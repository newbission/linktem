# Linktem Web — 로컬/셀프호스팅용 (Vercel 배포에는 사용하지 않음)
# 빌드 컨텍스트: 모노레포 루트 (packages/types 필요)
FROM node:20-alpine AS build
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
WORKDIR /repo

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/types/package.json packages/types/
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile

COPY packages/types packages/types
COPY apps/web apps/web

# 비워 두면 같은 출처 /api 로 호출하고 Next 서버가 API_PROXY_TARGET(런타임 env)으로 프록시 (권장)
ARG NEXT_PUBLIC_API_BASE_URL=
ARG NEXT_PUBLIC_SITE_URL=
ARG NEXT_PUBLIC_DONATION_URL=
ARG NEXT_PUBLIC_ADSENSE_CLIENT=
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_DONATION_URL=$NEXT_PUBLIC_DONATION_URL \
    NEXT_PUBLIC_ADSENSE_CLIENT=$NEXT_PUBLIC_ADSENSE_CLIENT \
    NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter @linktem/web... run build

FROM node:20-alpine AS runtime
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
