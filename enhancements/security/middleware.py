#!/usr/bin/env python3
"""
Security Middleware for NornFlow Flask Applications.

This module provides comprehensive security middleware:
- Authentication and authorization
- Session management
- RBAC integration
- API endpoint protection
- Security headers and CORS

Features:
- JWT token authentication
- Session-based authentication
- Role-based access control
- API rate limiting
- Security headers enforcement
- CORS configuration
"""

import jwt
import json
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, List, Callable
from flask import Flask, request, jsonify, session, g
import logging

from .rbac import RBACManager, Permission, ResourceType, AccessRequest

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """
    Security middleware for Flask applications.
    
    Provides:
    - Authentication (JWT and session-based)
    - Authorization (RBAC integration)
    - Security headers
    - Rate limiting
    - CORS configuration
    """
    
    def __init__(self, app: Flask = None, config: Dict[str, Any] = None):
        """Initialize security middleware."""
        self.config = config or {}
        self.rbac_manager = None
        
        # JWT configuration
        self.jwt_secret = self.config.get("jwt_secret", "nornflow-secret-key")
        self.jwt_algorithm = self.config.get("jwt_algorithm", "HS256")
        self.jwt_expiration_hours = self.config.get("jwt_expiration_hours", 24)
        
        # Session configuration
        self.session_timeout_minutes = self.config.get("session_timeout_minutes", 60)
        
        # Rate limiting
        self.rate_limit_enabled = self.config.get("rate_limit_enabled", True)
        self.rate_limit_requests = self.config.get("rate_limit_requests", 100)
        self.rate_limit_window = self.config.get("rate_limit_window", 3600)  # 1 hour
        self.rate_limit_storage = {}
        
        # Security headers
        self.security_headers = self.config.get("security_headers", {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'"
        })
        
        # CORS configuration
        self.cors_enabled = self.config.get("cors_enabled", True)
        self.cors_origins = self.config.get("cors_origins", ["*"])
        self.cors_methods = self.config.get("cors_methods", ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        self.cors_headers = self.config.get("cors_headers", ["Content-Type", "Authorization"])
        
        # Initialize RBAC
        rbac_config = self.config.get("rbac", {})
        if rbac_config:
            self.rbac_manager = RBACManager(rbac_config)
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize middleware with Flask app."""
        self.app = app
        
        # Configure session
        app.config["SECRET_KEY"] = self.config.get("session_secret", "nornflow-session-secret")
        app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=self.session_timeout_minutes)
        
        # Register middleware
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        # Register authentication routes
        self._register_auth_routes(app)
    
    def _before_request(self):
        """Process request before handling."""
        # Skip security for authentication endpoints
        if request.endpoint in ["auth.login", "auth.logout", "auth.refresh"]:
            return
        
        # Apply rate limiting
        if self.rate_limit_enabled and not self._check_rate_limit():
            return jsonify({
                "error": "Rate limit exceeded",
                "message": "Too many requests"
            }), 429
        
        # Handle CORS preflight
        if request.method == "OPTIONS" and self.cors_enabled:
            return self._handle_cors_preflight()
        
        # Check authentication for protected endpoints
        if self._requires_authentication():
            auth_result = self._authenticate_request()
            if not auth_result["authenticated"]:
                return jsonify({
                    "error": "Authentication required",
                    "message": auth_result["message"]
                }), 401
            
            # Store user info in request context
            g.current_user = auth_result["user"]
            g.authenticated = True
        else:
            g.authenticated = False
    
    def _after_request(self, response):
        """Process response after handling."""
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add CORS headers
        if self.cors_enabled:
            self._add_cors_headers(response)
        
        return response
    
    def _register_auth_routes(self, app: Flask):
        """Register authentication routes."""
        from flask import Blueprint
        
        auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
        
        @auth_bp.route("/login", methods=["POST"])
        def login():
            """User login endpoint."""
            try:
                data = request.get_json()
                username = data.get("username")
                password = data.get("password")
                
                if not username or not password:
                    return jsonify({
                        "success": False,
                        "message": "Username and password required"
                    }), 400
                
                # Authenticate with RBAC manager
                if not self.rbac_manager:
                    return jsonify({
                        "success": False,
                        "message": "Authentication system not configured"
                    }), 500
                
                auth_result = self.rbac_manager.authenticate_user(username, password)
                
                if not auth_result["success"]:
                    return jsonify(auth_result), 401
                
                user = auth_result["user"]
                
                # Generate JWT token
                token = self._generate_jwt_token(user)
                
                # Set session
                session["user"] = user
                session["authenticated"] = True
                session.permanent = True
                
                return jsonify({
                    "success": True,
                    "message": "Login successful",
                    "token": token,
                    "user": {
                        "username": user["username"],
                        "email": user["email"],
                        "roles": user["roles"]
                    }
                })
            
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                return jsonify({
                    "success": False,
                    "message": "Login failed"
                }), 500
        
        @auth_bp.route("/logout", methods=["POST"])
        def logout():
            """User logout endpoint."""
            session.clear()
            return jsonify({
                "success": True,
                "message": "Logout successful"
            })
        
        @auth_bp.route("/refresh", methods=["POST"])
        def refresh():
            """Refresh JWT token."""
            try:
                # Check if user is authenticated
                if not g.get("authenticated"):
                    return jsonify({
                        "success": False,
                        "message": "Authentication required"
                    }), 401
                
                user = g.current_user
                token = self._generate_jwt_token(user)
                
                return jsonify({
                    "success": True,
                    "token": token
                })
            
            except Exception as e:
                logger.error(f"Token refresh error: {str(e)}")
                return jsonify({
                    "success": False,
                    "message": "Token refresh failed"
                }), 500
        
        @auth_bp.route("/me", methods=["GET"])
        def me():
            """Get current user info."""
            if not g.get("authenticated"):
                return jsonify({
                    "success": False,
                    "message": "Authentication required"
                }), 401
            
            user = g.current_user
            return jsonify({
                "success": True,
                "user": {
                    "username": user["username"],
                    "email": user["email"],
                    "roles": user["roles"]
                }
            })
        
        app.register_blueprint(auth_bp)
    
    def _requires_authentication(self) -> bool:
        """Check if current endpoint requires authentication."""
        # Skip authentication for static files and health checks
        if request.endpoint in ["static", "health"]:
            return False
        
        # Check configuration
        return self.config.get("require_authentication", True)
    
    def _authenticate_request(self) -> Dict[str, Any]:
        """Authenticate current request."""
        # Try JWT authentication first
        jwt_result = self._authenticate_jwt()
        if jwt_result["authenticated"]:
            return jwt_result
        
        # Try session authentication
        session_result = self._authenticate_session()
        if session_result["authenticated"]:
            return session_result
        
        return {
            "authenticated": False,
            "message": "No valid authentication found"
        }
    
    def _authenticate_jwt(self) -> Dict[str, Any]:
        """Authenticate using JWT token."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {
                "authenticated": False,
                "message": "No JWT token provided"
            }
        
        token = auth_header.split(" ")[1]
        
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                return {
                    "authenticated": False,
                    "message": "JWT token expired"
                }
            
            # Get user info
            username = payload.get("username")
            if not username:
                return {
                    "authenticated": False,
                    "message": "Invalid JWT token"
                }
            
            # Verify user still exists and is active
            if self.rbac_manager and username in self.rbac_manager.users:
                user = self.rbac_manager.users[username]
                if not user.active:
                    return {
                        "authenticated": False,
                        "message": "User account is disabled"
                    }
                
                return {
                    "authenticated": True,
                    "user": user.to_dict(),
                    "method": "jwt"
                }
            
            return {
                "authenticated": False,
                "message": "User not found"
            }
        
        except jwt.InvalidTokenError:
            return {
                "authenticated": False,
                "message": "Invalid JWT token"
            }
        except Exception as e:
            logger.error(f"JWT authentication error: {str(e)}")
            return {
                "authenticated": False,
                "message": "JWT authentication failed"
            }
    
    def _authenticate_session(self) -> Dict[str, Any]:
        """Authenticate using session."""
        if not session.get("authenticated"):
            return {
                "authenticated": False,
                "message": "No active session"
            }
        
        user_data = session.get("user")
        if not user_data:
            return {
                "authenticated": False,
                "message": "No user data in session"
            }
        
        # Verify user still exists and is active
        if self.rbac_manager:
            username = user_data.get("username")
            if username in self.rbac_manager.users:
                user = self.rbac_manager.users[username]
                if not user.active:
                    session.clear()
                    return {
                        "authenticated": False,
                        "message": "User account is disabled"
                    }
                
                return {
                    "authenticated": True,
                    "user": user.to_dict(),
                    "method": "session"
                }
        
        return {
            "authenticated": True,
            "user": user_data,
            "method": "session"
        }
    
    def _generate_jwt_token(self, user: Dict[str, Any]) -> str:
        """Generate JWT token for user."""
        payload = {
            "username": user["username"],
            "email": user["email"],
            "roles": user["roles"],
            "iat": time.time(),
            "exp": time.time() + (self.jwt_expiration_hours * 3600)
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limits."""
        client_ip = request.remote_addr
        current_time = time.time()
        
        # Clean old entries
        cutoff_time = current_time - self.rate_limit_window
        self.rate_limit_storage = {
            ip: requests for ip, requests in self.rate_limit_storage.items()
            if any(req_time > cutoff_time for req_time in requests)
        }
        
        # Check current IP
        if client_ip not in self.rate_limit_storage:
            self.rate_limit_storage[client_ip] = []
        
        # Remove old requests for this IP
        self.rate_limit_storage[client_ip] = [
            req_time for req_time in self.rate_limit_storage[client_ip]
            if req_time > cutoff_time
        ]
        
        # Check if limit exceeded
        if len(self.rate_limit_storage[client_ip]) >= self.rate_limit_requests:
            return False
        
        # Add current request
        self.rate_limit_storage[client_ip].append(current_time)
        return True
    
    def _handle_cors_preflight(self):
        """Handle CORS preflight request."""
        response = jsonify({})
        self._add_cors_headers(response)
        return response
    
    def _add_cors_headers(self, response):
        """Add CORS headers to response."""
        if self.cors_enabled:
            origin = request.headers.get("Origin")
            if origin and (origin in self.cors_origins or "*" in self.cors_origins):
                response.headers["Access-Control-Allow-Origin"] = origin
            elif "*" in self.cors_origins:
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.cors_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.cors_headers)
            response.headers["Access-Control-Allow-Credentials"] = "true"
    
    def require_permission(self, permission: Permission, resource_type: ResourceType = None, resource_id: str = None):
        """
        Decorator to require specific permission for endpoint access.
        
        Args:
            permission: Required permission
            resource_type: Resource type for authorization
            resource_id: Specific resource ID (can be dynamic)
            
        Returns:
            Decorator function
        """
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Check if user is authenticated
                if not g.get("authenticated"):
                    return jsonify({
                        "error": "Authentication required",
                        "message": "You must be logged in to access this resource"
                    }), 401
                
                # Check authorization
                if self.rbac_manager:
                    user = g.current_user
                    
                    # Resolve dynamic resource ID
                    actual_resource_id = resource_id
                    if callable(resource_id):
                        actual_resource_id = resource_id(*args, **kwargs)
                    elif resource_id and resource_id.startswith("{"):
                        # Extract from URL parameters
                        param_name = resource_id.strip("{}")
                        actual_resource_id = kwargs.get(param_name) or request.view_args.get(param_name)
                    
                    # Create access request
                    access_request = AccessRequest(
                        user=user["username"],
                        permission=permission,
                        resource_type=resource_type or ResourceType.SYSTEM,
                        resource_id=actual_resource_id,
                        context={
                            "endpoint": request.endpoint,
                            "method": request.method,
                            "ip": request.remote_addr
                        }
                    )
                    
                    # Check authorization
                    access_result = self.rbac_manager.authorize_access(access_request)
                    
                    if not access_result.granted:
                        return jsonify({
                            "error": "Access denied",
                            "message": access_result.reason
                        }), 403
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    def require_role(self, *roles: str):
        """
        Decorator to require specific roles for endpoint access.
        
        Args:
            roles: Required roles
            
        Returns:
            Decorator function
        """
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Check if user is authenticated
                if not g.get("authenticated"):
                    return jsonify({
                        "error": "Authentication required",
                        "message": "You must be logged in to access this resource"
                    }), 401
                
                # Check roles
                user = g.current_user
                user_roles = set(user.get("roles", []))
                required_roles = set(roles)
                
                if not user_roles.intersection(required_roles):
                    return jsonify({
                        "error": "Access denied",
                        "message": f"Requires one of the following roles: {', '.join(roles)}"
                    }), 403
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
