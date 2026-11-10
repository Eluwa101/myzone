from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://crm:crm@localhost:5432/crm"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    groq_api_key: str | None = None
    open_router_api_key: str | None = None
    google_api_key: str | None = None

    # comma-separated list of allowed frontend origins, e.g.
    # "http://localhost:5173,https://your-app.vercel.app"
    cors_origins: str = "http://localhost:5173"

    # the frontend origin used to build links in emails (verify/reset) - the
    # first entry of cors_origins by default, but settable independently in
    # case the CORS list ever has more than one real frontend
    frontend_url: str = "http://localhost:5173"

    resend_api_key: str | None = None
    # Resend's shared test sender - works without verifying a domain, but
    # only delivers to the email address that owns the Resend account. Swap
    # for "YourBrand <noreply@yourdomain.com>" once a domain is verified.
    email_from: str = "MyShop <onboarding@resend.dev>"

    # the OAuth client ID from Google Cloud Console (Authorized JavaScript
    # origins must include every frontend origin in cors_origins) - used to
    # verify the audience of ID tokens from the "Continue with Google" button
    google_oauth_client_id: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
