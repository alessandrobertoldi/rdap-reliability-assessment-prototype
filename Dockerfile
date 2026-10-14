FROM python:3.13-slim
LABEL org.opencontainers.image.title="rdap-ra-proto" \
      org.opencontainers.image.description="Test RDAP server for the reliabilityAssessment extension" \
      org.opencontainers.image.licenses="BSD-2-Clause"
RUN useradd --system --no-create-home rdap
WORKDIR /app
COPY server/ /app/server/
COPY client/ /app/client/
USER rdap
ENV RDAP_BASE_URL=http://localhost:8080
EXPOSE 8080
ENTRYPOINT ["python3", "/app/server/rdap_ra_server.py"]
CMD ["--port", "8080"]
