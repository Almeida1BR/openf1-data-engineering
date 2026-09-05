DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'openf1_leitura') THEN
        CREATE ROLE openf1_leitura LOGIN PASSWORD 'leitura_local';
    END IF;
END
$$;
GRANT CONNECT ON DATABASE openf1 TO openf1_leitura;
GRANT USAGE ON SCHEMA analytics TO openf1_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO openf1_leitura;
ALTER DEFAULT PRIVILEGES FOR ROLE openf1 IN SCHEMA analytics GRANT SELECT ON TABLES TO openf1_leitura;
