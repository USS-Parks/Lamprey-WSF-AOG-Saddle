# Production-neutral Saddle runtime image. Runtime configuration and trust
# material are injected by the deployment profile; none are baked into it.
FROM rust:1-bookworm@sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663 AS builder
WORKDIR /build
COPY . .
RUN cargo build --release --locked \
    -p saddled \
    -p saddle-noded \
    -p saddlectl \
    -p wsf-api --bins \
    -p aog-gateway

FROM debian:bookworm-slim@sha256:60eac759739651111db372c07be67863818726f754804b8707c90979bda511df AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home saddle

COPY --from=builder /build/target/release/saddled /usr/local/bin/saddled
COPY --from=builder /build/target/release/saddle-noded /usr/local/bin/saddle-noded
COPY --from=builder /build/target/release/saddlectl /usr/local/bin/saddlectl
COPY --from=builder /build/target/release/wsf-api /usr/local/bin/wsf-api
COPY --from=builder /build/target/release/wsf-seed /usr/local/bin/wsf-seed
COPY --from=builder /build/target/release/aog-gateway /usr/local/bin/aog-gateway

USER saddle
ENTRYPOINT ["/usr/local/bin/saddled"]
