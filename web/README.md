# Exchange Game Web

Next.js frontend for the exchange game API.

## Run

```bash
npm install
npm run dev
```

The frontend proxies API requests through `/api/backend/*`.

Set the backend URL if it is not running on `http://localhost:8000`:

```bash
EXCHANGE_GAME_API_URL=http://localhost:8000 npm run dev
```
