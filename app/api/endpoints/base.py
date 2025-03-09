from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.routing import APIRoute
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
import logging
from app.users.dependencies.auth import admin_required

logger = logging.getLogger("advanced-router")

class ProtectedMethodsRoute(APIRoute):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_extra_metadata()

    def _add_extra_metadata(self):
        """Автоматическое добавление метаданных для документации Swagger"""
        if not self.endpoint.__doc__:
            if self.dependencies:
                self.endpoint.__doc__ = "🔒 Protected endpoint (requires admin access)"
            else:
                self.endpoint.__doc__ = "🌍 Public endpoint"

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()
        protected_methods = ["POST", "PUT", "DELETE"]

        async def custom_route_handler(request: Request, admin_data: dict = Depends(admin_required)):
            start_time = datetime.now()
            try:
                if request.method in protected_methods:
                    print(f"Checking admin for {request.method} {request.url}")
                    request.state.admin = admin_data
                    print(f"Admin check passed for {request.url} with state: {request.state.admin}")
                response = await original_handler(request)
                exec_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"{request.method} {request.url} - {response.status_code} ({exec_time:.2f}s)")
                return response
            except HTTPException as e:
                logger.error(f"Error in {request.method} {request.url}: {e.detail}")
                raise

        return custom_route_handler

class SecureRouter(APIRouter):
    def __init__(
            self,
            *,
            version: int = 1,
            auto_protect: bool = True,
            default_dependencies: Optional[List[Depends]] = None,
            **kwargs
    ):
        kwargs.pop("route_class", None)
        user_prefix = kwargs.pop("prefix", "")
        full_prefix = f"/v{version}{user_prefix}"

        super().__init__(
            prefix=full_prefix,
            route_class=ProtectedMethodsRoute,
            **kwargs
        )

        self.auto_protect = auto_protect
        self.default_dependencies = default_dependencies or []

    def add_api_route(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        dependencies = kwargs.get("dependencies", []) or []

        if self.auto_protect and kwargs.get("methods") != ["GET"]:
            dependencies.extend(self.default_dependencies)

        unique_dependencies = []
        seen = set()
        for dep in dependencies:
            if dep.dependency not in seen:
                seen.add(dep.dependency)
                unique_dependencies.append(dep)

        kwargs["dependencies"] = unique_dependencies

        super().add_api_route(path, endpoint, **kwargs)