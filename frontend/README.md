# MyShop frontend

The MyShop frontend is the React web application for managing customer relationships and sales activity. It connects to the FastAPI backend and provides the CRM interface, dashboards, settings, and AI chat experiences.

## Features

- Sign up and sign in to an organization workspace.
- Browse and manage customer records, including duplicate review and merge flows.
- View customer transactions and dashboard summaries.
- Import and export customer data as CSV.
- Use the general CRM assistant and the separate read-only Ask Your Data chat.
- Reopen saved assistant conversations; use voice input in browsers that support the Web Speech API.
- Configure WhatsApp contact details and generate a QR code.

The frontend is built with React, TypeScript, and Vite. Markdown responses are rendered in chat. The general assistant can display image-enabled interactions supported by the backend and configured model provider.

## Run locally

Install dependencies and start the Vite development server:

```bash
npm install
npm run dev
```

Open the local URL printed by Vite (typically <http://localhost:5173>). The backend must be running, and its `CORS_ORIGINS` environment variable must allow the frontend's origin. See the [root README](../README.md) for the full-stack setup and the [backend guide](../backend/README.md) for API configuration.

## Checks

Build the production frontend:

```bash
npm run build
```

Run the linter:

```bash
npm run lint
```

## Configuration and deployment

The frontend is configured for deployment on Vercel; `vercel.json` provides the single-page-app rewrite. The API URL and deployment environment settings should match the backend deployment and its CORS configuration.
