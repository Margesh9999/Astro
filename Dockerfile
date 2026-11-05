# AstroTrader Next.js frontend (standalone). Point it at the backend with ASTRO_BACKEND_URL.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json bun.lock ./
RUN npm install -g bun && bun install
COPY . .
RUN npx next build && cp -r .next/static .next/standalone/.next/ && cp -r public .next/standalone/

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
EXPOSE 3000
CMD ["node", "server.js"]
