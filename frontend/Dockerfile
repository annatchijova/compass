# syntax=docker/dockerfile:1
# Multi-stage build for the COMPASS Next.js frontend, producing a slim
# standalone image suitable for Cloud Run (which injects $PORT).

# ---- deps: install production + dev deps for the build ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install

# ---- build: compile the standalone Next.js output ----
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_API_URL is inlined at build time. Default points at the live
# COMPASS backend on Cloud Run; override with
#   --build-arg NEXT_PUBLIC_API_URL=https://api.example.com
# Local dev uses .env.local instead of this Docker ARG.
ARG NEXT_PUBLIC_API_URL=https://compass-1028999311218.us-central1.run.app
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runner: minimal runtime image ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Cloud Run injects PORT; default to 8080 for local runs.
ENV PORT=8080
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

# Standalone server + static assets + public dir.
COPY --from=build /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 8080
# server.js reads $PORT and $HOSTNAME.
CMD ["node", "server.js"]
