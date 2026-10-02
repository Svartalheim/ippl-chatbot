-- Database terpisah untuk Keycloak (dijalankan sekali saat volume pertama kali dibuat)
SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec
