from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SafeJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "core.authentication.SafeJWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
