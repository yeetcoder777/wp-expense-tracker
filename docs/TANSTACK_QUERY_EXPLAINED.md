# TanStack Query explained: our expense dashboard

Updated: 19 October 2026. This describes the actual React implementation in
`expense-tracker - Copy`, following the frontend/backend directory split.

## 1. What it does

TanStack Query manages data fetched from the backend: it caches successful
responses, shares them across components and refreshes them when necessary.
We use `@tanstack/react-query` v5. React Query is its earlier name.

`fetch()` sends HTTP requests. TanStack Query manages their results and lifecycle.
FastAPI and the database remain responsible for authoritative financial operations.

## 2. Analogy: a bank clerk's notebook

Imagine asking a clerk for your October transaction list.

| Project component | Analogy |
| --- | --- |
| Database | Bank's authoritative ledger |
| FastAPI | Counter processing requests |
| fetch() | Messenger carrying requests and responses |
| TanStack Query cache | Notebook containing recent answers |
| Query key | Notebook label: customer, report and filters |
| Invalidation | Marking a copy outdated after a change |

The first time you ask, the clerk gets a fresh copy and records it. If you ask
again soon, they can show that copy immediately. After you edit a transaction,
the clerk marks related copies outdated and requests replacements.

A WhatsApp transaction arriving elsewhere does not magically update the notebook.
The clerk must check again or receive a notification. Currently our app checks
on certain events or manual Refresh; instant notifications are not implemented.

## 3. Why we used it

A basic component can fetch inside useEffect and store results in useState.
When that component remounts, it may request the same information again. Sharing
responses, managing freshness and refreshing related reports then require more code.

Our React redesign already used Query. The later caching update changed its
policy: ledger freshness increased from 30 seconds to five minutes, inactive
retention increased from the default five minutes to thirty minutes, stale-data
focus revalidation was enabled, and a Refresh button was added.

This reduces repeat requests and makes revisiting cached views feel immediate.
No numerical performance improvement has been measured.

## 4. Files and request flow

| File, relative to project root | Responsibility |
| --- | --- |
| frontend/src/main.jsx | Shared QueryClient and provider |
| frontend/src/hooks/useLedger.js | Query/mutation wrappers |
| frontend/src/api/client.js | HTTP requests, errors, timeout and account checks |
| frontend/src/auth/AuthContext.jsx | Authentication and cache cleanup |
| frontend/src/App.jsx | Refresh control |
| frontend/src/pages/Imports.jsx | Import confirmation and invalidation |

```text
React page -> useLedgerQuery -> shared cache
                                 |
                      fresh hit: display immediately
                                 |
                      request needed: API client
                                 |
                      fetch -> FastAPI -> database
                                 |
                      cache response -> render
```

The cache is in the browser. No Redis or backend caching layer was added.

## 5. QueryClient and provider

Actual configuration from main.jsx:

```jsx
const client = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
  },
});
```

We create the client outside component rendering so ordinary renders do not
recreate the cache. QueryClientProvider makes it accessible throughout the app:

```jsx
<QueryClientProvider client={client}>
  <AuthProvider>
    <ToastProvider>
      <App />
    </ToastProvider>
  </AuthProvider>
</QueryClientProvider>
```

## 6. staleTime versus gcTime

| Setting | Meaning | Our value |
| --- | --- | --- |
| staleTime | How long a successful response is considered fresh | 5 minutes |
| gcTime | Retention after a query becomes inactive | 30 minutes |

Stale means eligible for refreshing, not deleted. Inactive means no mounted
component observes that query. Another component may still use it after leaving a page.

Neither setting is a polling interval. Crossing the freshness deadline alone
does not send a request. Mounting a stale query, returning browser focus or
reconnecting can trigger revalidation. Explicit invalidation can override freshness.

```text
10:00  Open October transactions -> fetch and cache
10:02  Reopen same query         -> fresh cache, no request needed
10:07  Reopen same query         -> cached display + background refresh
Later  Unused for 30 minutes     -> eligible for removal
```

An always-open focused page does not automatically refresh every five minutes.

## 7. Query keys identify results

Our hook uses:

```jsx
queryKey: [user?.account_id, name, params]
```

Example:

```jsx
[
  'example-account',
  'transactions',
  { currency: 'INR', category: 'food', limit: 25, offset: 0 },
]
```

Accounts, resources and filters each affect the result, so they all belong in
the key. Different months, currencies or offsets get separate entries. Keys are
compared using their serializable contents; a new object with the same values
does not by itself create a new query.

Components using the same key share a query/result and can share an in-flight
request. Different parameters do not deduplicate: a six-row overview and a
25-row transaction page have separate entries. We did not create a normalized
entity store that automatically merges every transaction across all lists.

## 8. useQuery: reading data

Pages use our custom hook:

```jsx
const budgets = useLedgerQuery('budgets');
const rows = useLedgerQuery('transactions', {
  currency: 'INR', limit: 25, offset: 0,
});
```

Simplified internal outline:

```jsx
useQuery({
  queryKey: [user?.account_id, name, params],
  enabled: Boolean(user) && enabled,
  queryFn: async ({ signal }) => {
    // Build the endpoint and return our json() API helper's result.
  },
  retry: false,
});
```

The actual implementation maps monthly to reports/monthly and currencies to
transactions/currencies, filters empty URL parameters, and passes the account ID
and AbortSignal to the API helper. enabled prevents automatic fetching before
sign-in or before necessary inputs exist. Ledger queries disable automatic retries.
The explicit preview account returns illustrative responses without real ledger calls.

| Returned property | Meaning |
| --- | --- |
| data | Current successful result, if present |
| error | Request error, if present |
| isPending | No successful result yet; includes disabled queries without data |
| isFetching | A request is running, including background refresh |
| refetch() | Explicitly request this query again |

Pages can show a placeholder for initial loading and retain cached content during
refreshing. Query provides state; components choose rendering. Some of our pages
show an error view if a refresh fails, even when older data remains in the cache.

## 9. useMutation: changing data

A mutation performs an action such as editing/deleting a transaction or creating
a budget. Our wrapper sends the request and invalidates after success.

Simplified outline (not the entire hook):

```jsx
useMutation({
  mutationFn: body => json(path, {
    method, body, accountId: user.account_id,
  }),
  onSuccess: () => client.invalidateQueries({
    queryKey: [user.account_id],
  }),
});
```

The real hook additionally handles dynamic paths, DELETE bodies and read-only
preview restrictions. Import confirmation performs equivalent invalidation separately.

## 10. Invalidation and consistency

```text
Edit expense -> backend confirms save -> invalidate account queries
                                          |
                          active queries refresh
                          inactive queries become stale
```

Invalidation marks matching results outdated; it does not immediately erase all
content. Active matches normally refetch. Inactive matches can refresh when used again.

We invalidate the whole account because changing an expense can affect lists,
monthly totals, category charts, budgets and currency options.

Trade-off: this keeps the implementation simple but may refresh unrelated data.
Future optimization could target affected resources/months more precisely.

We did not implement optimistic updates. The backend confirms a change before
our success handler requests refreshed data; there is no optimistic rollback flow.

## 11. Manual Refresh and external WhatsApp updates

The header uses useIsFetching to count requests for the account and disables
Refresh while matching requests are running. Clicking Refresh invokes:

```jsx
queryClient.invalidateQueries({ queryKey: [user.account_id] });
```

WhatsApp writes occur outside this browser's query client. Those changes appear
on manual Refresh or an eligible stale-query revalidation. We did not add periodic
polling, server revision checks, SSE, WebSockets or cross-tab cache broadcasting.

A future server change notification could invalidate affected queries without
requiring repeated full-data polling. That is a possible improvement, not a current feature.

## 12. Authentication and cancellation

- Account ID in keys helps prevent cached records from being mixed.
- Accepting an account, signing out or expiring a session cancels queries and clears the cache.
- The query AbortSignal reaches fetch. The API helper also has a 25-second request timeout.
- Requests use same-origin session cookies, X-Ledger-Request and response account-marker checks.
- Authentication tokens are not stored in frontend localStorage.

Backend authentication and ownership checks enforce authorization. Cache keys
help UI isolation but do not replace server access control.

## 13. HTTP cache versus application cache

Our HTTP helper uses cache: 'no-store'; backend API responses also use no-store
headers. This controls HTTP caching by browsers/intermediaries.

Query's successful parsed responses are separately held in application memory.
Those settings coexist: fresh Query results can avoid a request entirely; when
we do request, we do not rely on a previously cached HTTP response.

Reloading creates a new client/cache. Different browser tabs have separate caches.
No financial-response persistence to localStorage was configured. Cached views
can help temporarily, but this is not a complete offline-capable application.

## 14. Interview explanation: about one minute

> I used TanStack Query to manage server state in the React expense dashboard.
> I created a shared QueryClient and reusable query/mutation hooks. Cache keys
> include account, resource and filters so users and views have separate entries.
> I configured five-minute freshness and thirty-minute inactive retention. Fresh
> results are reused across navigation; stale data can stay visible during
> background refreshes. Successful changes invalidate account queries so reports,
> transactions and budgets stay consistent. Authentication changes clear the
> cache. WhatsApp updates currently use eventual synchronization through refresh
> or revalidation; real-time notifications would be a future improvement.

## 15. Interview questions

**Why not only useState/useEffect?**
We use React state for local interactions. Remote data also needs cache identity,
sharing, freshness, errors, cancellation and invalidation; Query handles that lifecycle.

**Why not Redux?**
Query addresses remote data directly, while ordinary React state handles local
interactions. Redux was not needed for this scope; these tools have different roles.

**Does it make SQL or GLiNER faster?**
No. It reduces repeat requests and improves cached navigation. It does not reduce
an individual database query or model inference time.

**Why five minutes?**
It is a tunable starting point for a personal ledger, balancing freshness and
requests. It is not a measured optimum or a guarantee of real-time freshness.

**How do you know whether data changed?**
Our own successful mutations invalidate it. External changes require revalidation
or notifications. We currently recheck rather than receive server notifications.

**What would you improve?**
Measure request counts and latency, narrow invalidation, then consider prefetching
or server notifications if justified. Do not describe those as implemented.

## 16. Validation boundary

The initial React production build passed before later cache/theme/layout updates.
This guide was cross-checked against current source, not a new browser interaction
or performance benchmark. No tests, provider calls, user writes, Docker commands
or deployments were performed for this documentation update.

## 17. Official references and project links

- [Defaults and freshness](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults)
- [Query keys](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys)
- [Query states](https://tanstack.com/query/latest/docs/framework/react/guides/queries)
- [Invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation)
- [Cancellation](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation)
- [Complete project context](../context.md)
- [Current startup guide](../README.md)
