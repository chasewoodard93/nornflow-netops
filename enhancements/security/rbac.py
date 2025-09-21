#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) System for NornFlow.

This module provides comprehensive RBAC functionality:
- User and role management
- Permission-based access control
- Resource-level authorization
- Integration with workflow execution
- Audit logging for access control events

Features:
- Hierarchical role system
- Fine-grained permissions
- Resource-based access control
- Integration with secrets management
- Workflow execution authorization
- API endpoint protection
"""

import json
import hashlib
import secrets
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Permission(Enum):
    """System permissions enumeration."""
    # Workflow permissions
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_DELETE = "workflow:delete"
    
    # Secret permissions
    SECRET_READ = "secret:read"
    SECRET_WRITE = "secret:write"
    SECRET_DELETE = "secret:delete"
    SECRET_ROTATE = "secret:rotate"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
    
    # User management permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    
    # Role management permissions
    ROLE_READ = "role:read"
    ROLE_WRITE = "role:write"
    ROLE_DELETE = "role:delete"
    
    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_WRITE = "audit:write"


class ResourceType(Enum):
    """Resource types for access control."""
    WORKFLOW = "workflow"
    SECRET = "secret"
    USER = "user"
    ROLE = "role"
    SYSTEM = "system"
    AUDIT = "audit"


@dataclass
class User:
    """User account representation."""
    username: str
    email: str
    password_hash: str
    roles: Set[str] = field(default_factory=set)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            "username": self.username,
            "email": self.email,
            "roles": list(self.roles),
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "failed_login_attempts": self.failed_login_attempts,
            "locked_until": self.locked_until.isoformat() if self.locked_until else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create user from dictionary."""
        user = cls(
            username=data["username"],
            email=data["email"],
            password_hash=data["password_hash"],
            roles=set(data.get("roles", [])),
            active=data.get("active", True),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            failed_login_attempts=data.get("failed_login_attempts", 0),
            metadata=data.get("metadata", {})
        )
        
        if data.get("last_login"):
            user.last_login = datetime.fromisoformat(data["last_login"])
        
        if data.get("locked_until"):
            user.locked_until = datetime.fromisoformat(data["locked_until"])
        
        return user


@dataclass
class Role:
    """Role definition with permissions."""
    name: str
    description: str
    permissions: Set[Permission] = field(default_factory=set)
    parent_roles: Set[str] = field(default_factory=set)
    resource_restrictions: Dict[ResourceType, List[str]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert role to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "parent_roles": list(self.parent_roles),
            "resource_restrictions": {
                rt.value: restrictions for rt, restrictions in self.resource_restrictions.items()
            },
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Role':
        """Create role from dictionary."""
        role = cls(
            name=data["name"],
            description=data["description"],
            permissions={Permission(p) for p in data.get("permissions", [])},
            parent_roles=set(data.get("parent_roles", [])),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            metadata=data.get("metadata", {})
        )
        
        # Convert resource restrictions
        restrictions = data.get("resource_restrictions", {})
        for rt_str, restriction_list in restrictions.items():
            try:
                rt = ResourceType(rt_str)
                role.resource_restrictions[rt] = restriction_list
            except ValueError:
                logger.warning(f"Unknown resource type: {rt_str}")
        
        return role


@dataclass
class AccessRequest:
    """Access request for authorization."""
    user: str
    permission: Permission
    resource_type: ResourceType
    resource_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessResult:
    """Result of access authorization."""
    granted: bool
    reason: str
    user: str
    permission: Permission
    resource_type: ResourceType
    resource_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class RBACManager:
    """
    Role-Based Access Control manager.
    
    Provides:
    - User and role management
    - Permission-based authorization
    - Resource-level access control
    - Audit logging for access events
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize RBAC manager."""
        self.config = config or {}
        self.users_file = Path(self.config.get("users_file", "users.json"))
        self.roles_file = Path(self.config.get("roles_file", "roles.json"))
        
        # Security settings
        self.password_min_length = self.config.get("password_min_length", 8)
        self.max_failed_attempts = self.config.get("max_failed_attempts", 5)
        self.lockout_duration = timedelta(minutes=self.config.get("lockout_duration_minutes", 30))
        
        # Data storage
        self.users: Dict[str, User] = {}
        self.roles: Dict[str, Role] = {}
        
        # Load existing data
        self._load_users()
        self._load_roles()
        
        # Create default roles if none exist
        if not self.roles:
            self._create_default_roles()
        
        # Audit logging
        self.audit_enabled = self.config.get("audit_enabled", True)
        if self.audit_enabled:
            self.audit_logger = logging.getLogger("nornflow.rbac.audit")
            self.audit_logger.setLevel(logging.INFO)
    
    def _load_users(self):
        """Load users from storage."""
        if not self.users_file.exists():
            return
        
        try:
            with open(self.users_file, 'r') as f:
                users_data = json.load(f)
            
            for username, user_data in users_data.items():
                user_data["password_hash"] = user_data.get("password_hash", "")
                self.users[username] = User.from_dict(user_data)
        
        except Exception as e:
            logger.error(f"Failed to load users: {str(e)}")
    
    def _save_users(self):
        """Save users to storage."""
        try:
            # Ensure directory exists
            self.users_file.parent.mkdir(parents=True, exist_ok=True)
            
            users_data = {}
            for username, user in self.users.items():
                user_dict = user.to_dict()
                user_dict["password_hash"] = user.password_hash
                users_data[username] = user_dict
            
            with open(self.users_file, 'w') as f:
                json.dump(users_data, f, indent=2, default=str)
        
        except Exception as e:
            logger.error(f"Failed to save users: {str(e)}")
    
    def _load_roles(self):
        """Load roles from storage."""
        if not self.roles_file.exists():
            return
        
        try:
            with open(self.roles_file, 'r') as f:
                roles_data = json.load(f)
            
            for role_name, role_data in roles_data.items():
                self.roles[role_name] = Role.from_dict(role_data)
        
        except Exception as e:
            logger.error(f"Failed to load roles: {str(e)}")
    
    def _save_roles(self):
        """Save roles to storage."""
        try:
            # Ensure directory exists
            self.roles_file.parent.mkdir(parents=True, exist_ok=True)
            
            roles_data = {}
            for role_name, role in self.roles.items():
                roles_data[role_name] = role.to_dict()
            
            with open(self.roles_file, 'w') as f:
                json.dump(roles_data, f, indent=2, default=str)
        
        except Exception as e:
            logger.error(f"Failed to save roles: {str(e)}")
    
    def _create_default_roles(self):
        """Create default system roles."""
        # Administrator role
        admin_role = Role(
            name="administrator",
            description="Full system administrator with all permissions",
            permissions=set(Permission),  # All permissions
        )
        
        # Network Engineer role
        engineer_role = Role(
            name="network_engineer",
            description="Network engineer with workflow and monitoring permissions",
            permissions={
                Permission.WORKFLOW_READ,
                Permission.WORKFLOW_WRITE,
                Permission.WORKFLOW_EXECUTE,
                Permission.SECRET_READ,
                Permission.SYSTEM_MONITOR,
                Permission.AUDIT_READ
            }
        )
        
        # Operator role
        operator_role = Role(
            name="operator",
            description="Network operator with execution and monitoring permissions",
            permissions={
                Permission.WORKFLOW_READ,
                Permission.WORKFLOW_EXECUTE,
                Permission.SECRET_READ,
                Permission.SYSTEM_MONITOR
            }
        )
        
        # Read-only role
        readonly_role = Role(
            name="readonly",
            description="Read-only access to workflows and monitoring",
            permissions={
                Permission.WORKFLOW_READ,
                Permission.SYSTEM_MONITOR,
                Permission.AUDIT_READ
            }
        )
        
        # Save default roles
        self.roles["administrator"] = admin_role
        self.roles["network_engineer"] = engineer_role
        self.roles["operator"] = operator_role
        self.roles["readonly"] = readonly_role
        
        self._save_roles()
        logger.info("Created default RBAC roles")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            salt, hash_value = password_hash.split(':', 1)
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed_hash == hash_value
        except ValueError:
            return False
    
    def _log_audit_event(self, event_type: str, user: str, details: Dict[str, Any]):
        """Log audit event."""
        if not self.audit_enabled:
            return
        
        audit_data = {
            "event_type": event_type,
            "user": user,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        
        self.audit_logger.info(json.dumps(audit_data))
    
    def create_user(self, username: str, email: str, password: str, roles: List[str] = None) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            username: Unique username
            email: User email address
            password: User password
            roles: List of role names to assign
            
        Returns:
            Creation result
        """
        # Validate input
        if username in self.users:
            return {
                "success": False,
                "message": f"User {username} already exists"
            }
        
        if len(password) < self.password_min_length:
            return {
                "success": False,
                "message": f"Password must be at least {self.password_min_length} characters"
            }
        
        # Validate roles
        user_roles = set()
        if roles:
            for role_name in roles:
                if role_name not in self.roles:
                    return {
                        "success": False,
                        "message": f"Role {role_name} does not exist"
                    }
                user_roles.add(role_name)
        
        try:
            # Create user
            password_hash = self._hash_password(password)
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                roles=user_roles
            )
            
            self.users[username] = user
            self._save_users()
            
            # Log audit event
            self._log_audit_event("user_created", "system", {
                "username": username,
                "email": email,
                "roles": list(user_roles)
            })
            
            logger.info(f"Created user: {username}")
            
            return {
                "success": True,
                "message": f"User {username} created successfully",
                "user": user.to_dict()
            }
        
        except Exception as e:
            logger.error(f"Failed to create user {username}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to create user: {str(e)}"
            }
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user credentials.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            Authentication result
        """
        if username not in self.users:
            self._log_audit_event("login_failed", username, {"reason": "user_not_found"})
            return {
                "success": False,
                "message": "Invalid credentials"
            }
        
        user = self.users[username]
        
        # Check if user is locked
        if user.locked_until and datetime.now() < user.locked_until:
            self._log_audit_event("login_failed", username, {"reason": "account_locked"})
            return {
                "success": False,
                "message": "Account is locked due to too many failed attempts"
            }
        
        # Check if user is active
        if not user.active:
            self._log_audit_event("login_failed", username, {"reason": "account_disabled"})
            return {
                "success": False,
                "message": "Account is disabled"
            }
        
        # Verify password
        if not self._verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            
            # Lock account if too many failed attempts
            if user.failed_login_attempts >= self.max_failed_attempts:
                user.locked_until = datetime.now() + self.lockout_duration
                logger.warning(f"Account {username} locked due to failed login attempts")
            
            self._save_users()
            self._log_audit_event("login_failed", username, {"reason": "invalid_password"})
            
            return {
                "success": False,
                "message": "Invalid credentials"
            }
        
        # Successful authentication
        user.last_login = datetime.now()
        user.failed_login_attempts = 0
        user.locked_until = None
        self._save_users()
        
        self._log_audit_event("login_success", username, {})
        
        return {
            "success": True,
            "message": "Authentication successful",
            "user": user.to_dict()
        }
    
    def authorize_access(self, request: AccessRequest) -> AccessResult:
        """
        Authorize access request.
        
        Args:
            request: Access request to authorize
            
        Returns:
            Authorization result
        """
        # Check if user exists
        if request.user not in self.users:
            result = AccessResult(
                granted=False,
                reason="User not found",
                user=request.user,
                permission=request.permission,
                resource_type=request.resource_type,
                resource_id=request.resource_id
            )
            
            self._log_audit_event("access_denied", request.user, {
                "permission": request.permission.value,
                "resource_type": request.resource_type.value,
                "resource_id": request.resource_id,
                "reason": "user_not_found"
            })
            
            return result
        
        user = self.users[request.user]
        
        # Check if user is active
        if not user.active:
            result = AccessResult(
                granted=False,
                reason="User account is disabled",
                user=request.user,
                permission=request.permission,
                resource_type=request.resource_type,
                resource_id=request.resource_id
            )
            
            self._log_audit_event("access_denied", request.user, {
                "permission": request.permission.value,
                "resource_type": request.resource_type.value,
                "resource_id": request.resource_id,
                "reason": "account_disabled"
            })
            
            return result
        
        # Check permissions through roles
        user_permissions = self._get_user_permissions(user)
        
        if request.permission not in user_permissions:
            result = AccessResult(
                granted=False,
                reason="Insufficient permissions",
                user=request.user,
                permission=request.permission,
                resource_type=request.resource_type,
                resource_id=request.resource_id
            )
            
            self._log_audit_event("access_denied", request.user, {
                "permission": request.permission.value,
                "resource_type": request.resource_type.value,
                "resource_id": request.resource_id,
                "reason": "insufficient_permissions"
            })
            
            return result
        
        # Check resource-level restrictions
        if not self._check_resource_access(user, request.resource_type, request.resource_id):
            result = AccessResult(
                granted=False,
                reason="Resource access denied",
                user=request.user,
                permission=request.permission,
                resource_type=request.resource_type,
                resource_id=request.resource_id
            )
            
            self._log_audit_event("access_denied", request.user, {
                "permission": request.permission.value,
                "resource_type": request.resource_type.value,
                "resource_id": request.resource_id,
                "reason": "resource_access_denied"
            })
            
            return result
        
        # Access granted
        result = AccessResult(
            granted=True,
            reason="Access granted",
            user=request.user,
            permission=request.permission,
            resource_type=request.resource_type,
            resource_id=request.resource_id
        )
        
        self._log_audit_event("access_granted", request.user, {
            "permission": request.permission.value,
            "resource_type": request.resource_type.value,
            "resource_id": request.resource_id
        })
        
        return result
    
    def _get_user_permissions(self, user: User) -> Set[Permission]:
        """Get all permissions for a user through their roles."""
        permissions = set()
        
        # Process all user roles (including inherited roles)
        roles_to_process = list(user.roles)
        processed_roles = set()
        
        while roles_to_process:
            role_name = roles_to_process.pop(0)
            
            if role_name in processed_roles or role_name not in self.roles:
                continue
            
            processed_roles.add(role_name)
            role = self.roles[role_name]
            
            # Add role permissions
            permissions.update(role.permissions)
            
            # Add parent roles to processing queue
            roles_to_process.extend(role.parent_roles)
        
        return permissions
    
    def _check_resource_access(self, user: User, resource_type: ResourceType, resource_id: Optional[str]) -> bool:
        """Check if user has access to specific resource."""
        # If no resource ID specified, allow access (permission check already passed)
        if not resource_id:
            return True
        
        # Check resource restrictions in user roles
        for role_name in user.roles:
            if role_name not in self.roles:
                continue
            
            role = self.roles[role_name]
            
            # If role has restrictions for this resource type
            if resource_type in role.resource_restrictions:
                restrictions = role.resource_restrictions[resource_type]
                
                # If restrictions list is empty, allow all resources
                if not restrictions:
                    return True
                
                # Check if resource ID matches any restriction pattern
                for pattern in restrictions:
                    if self._match_resource_pattern(resource_id, pattern):
                        return True
                
                # If restrictions exist but no match found, deny access
                return False
        
        # No restrictions found, allow access
        return True
    
    def _match_resource_pattern(self, resource_id: str, pattern: str) -> bool:
        """Match resource ID against pattern (supports wildcards)."""
        if pattern == "*":
            return True
        
        if "*" in pattern:
            # Simple wildcard matching
            import fnmatch
            return fnmatch.fnmatch(resource_id, pattern)
        
        return resource_id == pattern
