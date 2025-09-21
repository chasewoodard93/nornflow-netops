#!/usr/bin/env python3
"""
Security Setup Utility for NornFlow.

This utility provides comprehensive security setup and configuration:
- Secrets management configuration
- RBAC system initialization
- Security policy configuration
- Integration testing and validation

Features:
- Automated security setup
- Provider configuration and testing
- User and role management
- Security policy enforcement
- Health checks and diagnostics

Usage:
    python security_setup.py --setup-secrets
    python security_setup.py --setup-rbac
    python security_setup.py --create-admin-user admin@example.com
    python security_setup.py --test-providers
    python security_setup.py --check-security
"""

import argparse
import json
import yaml
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List
import logging
import getpass

from .secrets_manager import UnifiedSecretsManager, SecretProvider
from .rbac import RBACManager, Permission, ResourceType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecuritySetup:
    """Security setup and configuration manager for NornFlow."""
    
    def __init__(self, config_file: Path = None):
        """Initialize security setup manager."""
        self.config_file = config_file or Path("security_config.yaml")
        self.config = self._load_or_create_config()
        
        # Default configuration
        self.default_config = {
            "secrets": {
                "provider_priority": ["vault", "aws_secrets", "azure_keyvault", "doppler", "local"],
                "audit_enabled": True,
                "audit_log_path": "secrets_audit.log",
                "providers": {
                    "vault": {
                        "url": "http://localhost:8200",
                        "token": "",
                        "mount_point": "secret"
                    },
                    "aws_secrets": {
                        "region": "us-east-1",
                        "access_key_id": "",
                        "secret_access_key": ""
                    },
                    "azure_keyvault": {
                        "vault_url": "",
                        "client_id": "",
                        "client_secret": "",
                        "tenant_id": ""
                    },
                    "doppler": {
                        "api_token": "",
                        "project": "",
                        "environment": "dev"
                    },
                    "local": {
                        "storage_path": "secrets.enc",
                        "password": ""
                    }
                }
            },
            "rbac": {
                "users_file": "users.json",
                "roles_file": "roles.json",
                "password_min_length": 8,
                "max_failed_attempts": 5,
                "lockout_duration_minutes": 30,
                "audit_enabled": True
            },
            "security_policies": {
                "require_authentication": True,
                "require_authorization": True,
                "session_timeout_minutes": 60,
                "password_complexity": {
                    "min_length": 8,
                    "require_uppercase": True,
                    "require_lowercase": True,
                    "require_numbers": True,
                    "require_special_chars": False
                }
            }
        }
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load existing config or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load config: {str(e)}, using defaults")
        
        return {}
    
    def create_config_file(self, force: bool = False) -> Dict[str, Any]:
        """
        Create security configuration file.
        
        Args:
            force: Overwrite existing config file
            
        Returns:
            Configuration creation result
        """
        if self.config_file.exists() and not force:
            return {
                "success": False,
                "message": f"Config file already exists: {self.config_file}. Use --force to overwrite."
            }
        
        try:
            # Merge with existing config
            config = {**self.default_config, **self.config}
            
            with open(self.config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Security configuration file created: {self.config_file}")
            
            return {
                "success": True,
                "config_file": str(self.config_file),
                "message": f"Security configuration file created successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to create config file: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to create config file: {str(e)}"
            }
    
    def setup_secrets_management(self) -> Dict[str, Any]:
        """
        Setup secrets management system.
        
        Returns:
            Setup result
        """
        logger.info("Setting up secrets management system...")
        
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            secrets_config = config.get("secrets", {})
            
            # Initialize secrets manager
            secrets_manager = UnifiedSecretsManager(secrets_config)
            
            # Test provider connectivity
            provider_status = secrets_manager.get_provider_status()
            
            available_providers = []
            failed_providers = []
            
            for provider, status in provider_status.items():
                if status["available"]:
                    available_providers.append(provider.value)
                else:
                    failed_providers.append({
                        "provider": provider.value,
                        "error": status["message"]
                    })
            
            logger.info(f"Available providers: {', '.join(available_providers)}")
            
            if failed_providers:
                logger.warning(f"Failed providers: {failed_providers}")
            
            return {
                "success": True,
                "message": "Secrets management setup completed",
                "available_providers": available_providers,
                "failed_providers": failed_providers
            }
        
        except Exception as e:
            logger.error(f"Secrets management setup failed: {str(e)}")
            return {
                "success": False,
                "message": f"Secrets management setup failed: {str(e)}"
            }
    
    def setup_rbac_system(self) -> Dict[str, Any]:
        """
        Setup RBAC system.
        
        Returns:
            Setup result
        """
        logger.info("Setting up RBAC system...")
        
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            rbac_config = config.get("rbac", {})
            
            # Initialize RBAC manager
            rbac_manager = RBACManager(rbac_config)
            
            # Check if default roles were created
            roles = list(rbac_manager.roles.keys())
            users = list(rbac_manager.users.keys())
            
            logger.info(f"RBAC system initialized with {len(roles)} roles and {len(users)} users")
            
            return {
                "success": True,
                "message": "RBAC system setup completed",
                "roles": roles,
                "users": users
            }
        
        except Exception as e:
            logger.error(f"RBAC system setup failed: {str(e)}")
            return {
                "success": False,
                "message": f"RBAC system setup failed: {str(e)}"
            }
    
    def create_admin_user(self, email: str, username: str = None, password: str = None) -> Dict[str, Any]:
        """
        Create administrator user.
        
        Args:
            email: Admin email address
            username: Admin username (defaults to 'admin')
            password: Admin password (prompts if not provided)
            
        Returns:
            User creation result
        """
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            rbac_config = config.get("rbac", {})
            
            # Initialize RBAC manager
            rbac_manager = RBACManager(rbac_config)
            
            # Set defaults
            if not username:
                username = "admin"
            
            if not password:
                password = getpass.getpass("Enter admin password: ")
                confirm_password = getpass.getpass("Confirm admin password: ")
                
                if password != confirm_password:
                    return {
                        "success": False,
                        "message": "Passwords do not match"
                    }
            
            # Create admin user
            result = rbac_manager.create_user(
                username=username,
                email=email,
                password=password,
                roles=["administrator"]
            )
            
            if result["success"]:
                logger.info(f"Administrator user '{username}' created successfully")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to create admin user: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to create admin user: {str(e)}"
            }
    
    async def test_secrets_providers(self) -> Dict[str, Any]:
        """
        Test all configured secrets providers.
        
        Returns:
            Test results
        """
        logger.info("Testing secrets providers...")
        
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            secrets_config = config.get("secrets", {})
            
            # Initialize secrets manager
            secrets_manager = UnifiedSecretsManager(secrets_config)
            
            test_results = {}
            test_key = "nornflow_test_secret"
            test_value = "test_value_123"
            
            for provider_type in secrets_manager.providers.keys():
                logger.info(f"Testing {provider_type.value} provider...")
                
                try:
                    # Test write
                    write_success = await secrets_manager.set_secret(
                        test_key, test_value, provider=provider_type
                    )
                    
                    if not write_success:
                        test_results[provider_type.value] = {
                            "success": False,
                            "message": "Failed to write test secret"
                        }
                        continue
                    
                    # Test read
                    secret = await secrets_manager.get_secret(test_key)
                    
                    if not secret or secret.value != test_value:
                        test_results[provider_type.value] = {
                            "success": False,
                            "message": "Failed to read test secret or value mismatch"
                        }
                        continue
                    
                    # Test delete
                    delete_success = await secrets_manager.delete_secret(
                        test_key, provider=provider_type
                    )
                    
                    test_results[provider_type.value] = {
                        "success": True,
                        "message": "All operations successful",
                        "operations": {
                            "write": write_success,
                            "read": True,
                            "delete": delete_success
                        }
                    }
                
                except Exception as e:
                    test_results[provider_type.value] = {
                        "success": False,
                        "message": f"Test failed: {str(e)}"
                    }
            
            # Overall success
            overall_success = any(result["success"] for result in test_results.values())
            
            return {
                "success": overall_success,
                "message": "Provider testing completed",
                "results": test_results
            }
        
        except Exception as e:
            logger.error(f"Provider testing failed: {str(e)}")
            return {
                "success": False,
                "message": f"Provider testing failed: {str(e)}"
            }
    
    def check_security_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive security health check.
        
        Returns:
            Health check results
        """
        logger.info("Performing security health check...")
        
        checks = {
            "config": self._check_config_security(),
            "secrets": self._check_secrets_security(),
            "rbac": self._check_rbac_security(),
            "policies": self._check_security_policies(),
            "files": self._check_file_permissions()
        }
        
        # Overall health
        overall_healthy = all(check["healthy"] for check in checks.values())
        
        return {
            "healthy": overall_healthy,
            "checks": checks,
            "message": "Security system healthy" if overall_healthy else "Security issues detected"
        }
    
    def _check_config_security(self) -> Dict[str, Any]:
        """Check configuration security."""
        try:
            if not self.config_file.exists():
                return {
                    "healthy": False,
                    "message": "Security configuration file not found"
                }
            
            # Check file permissions
            file_stat = self.config_file.stat()
            if file_stat.st_mode & 0o077:  # Check if readable by others
                return {
                    "healthy": False,
                    "message": "Configuration file has insecure permissions"
                }
            
            # Check for empty passwords/tokens
            config = {**self.default_config, **self.config}
            secrets_config = config.get("secrets", {}).get("providers", {})
            
            empty_credentials = []
            for provider, provider_config in secrets_config.items():
                if provider == "local":
                    continue
                
                for key, value in provider_config.items():
                    if "token" in key or "password" in key or "secret" in key:
                        if not value:
                            empty_credentials.append(f"{provider}.{key}")
            
            if empty_credentials:
                return {
                    "healthy": False,
                    "message": f"Empty credentials found: {', '.join(empty_credentials)}"
                }
            
            return {
                "healthy": True,
                "message": "Configuration security OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Config security check failed: {str(e)}"
            }
    
    def _check_secrets_security(self) -> Dict[str, Any]:
        """Check secrets management security."""
        try:
            config = {**self.default_config, **self.config}
            secrets_config = config.get("secrets", {})
            
            # Check if audit is enabled
            if not secrets_config.get("audit_enabled", True):
                return {
                    "healthy": False,
                    "message": "Secrets audit logging is disabled"
                }
            
            # Check local storage encryption
            local_config = secrets_config.get("providers", {}).get("local", {})
            if not local_config.get("password"):
                return {
                    "healthy": False,
                    "message": "Local secrets storage has no encryption password"
                }
            
            return {
                "healthy": True,
                "message": "Secrets security OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Secrets security check failed: {str(e)}"
            }
    
    def _check_rbac_security(self) -> Dict[str, Any]:
        """Check RBAC security."""
        try:
            config = {**self.default_config, **self.config}
            rbac_config = config.get("rbac", {})
            
            # Check password requirements
            min_length = rbac_config.get("password_min_length", 8)
            if min_length < 8:
                return {
                    "healthy": False,
                    "message": "Password minimum length is too short"
                }
            
            # Check if audit is enabled
            if not rbac_config.get("audit_enabled", True):
                return {
                    "healthy": False,
                    "message": "RBAC audit logging is disabled"
                }
            
            return {
                "healthy": True,
                "message": "RBAC security OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"RBAC security check failed: {str(e)}"
            }
    
    def _check_security_policies(self) -> Dict[str, Any]:
        """Check security policies."""
        try:
            config = {**self.default_config, **self.config}
            policies = config.get("security_policies", {})
            
            # Check if authentication is required
            if not policies.get("require_authentication", True):
                return {
                    "healthy": False,
                    "message": "Authentication is not required"
                }
            
            # Check if authorization is required
            if not policies.get("require_authorization", True):
                return {
                    "healthy": False,
                    "message": "Authorization is not required"
                }
            
            return {
                "healthy": True,
                "message": "Security policies OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Security policies check failed: {str(e)}"
            }
    
    def _check_file_permissions(self) -> Dict[str, Any]:
        """Check file permissions for security files."""
        try:
            security_files = [
                "users.json",
                "roles.json", 
                "secrets.enc",
                "secrets_audit.log"
            ]
            
            insecure_files = []
            
            for filename in security_files:
                file_path = Path(filename)
                if file_path.exists():
                    file_stat = file_path.stat()
                    if file_stat.st_mode & 0o077:  # Check if readable by others
                        insecure_files.append(filename)
            
            if insecure_files:
                return {
                    "healthy": False,
                    "message": f"Insecure file permissions: {', '.join(insecure_files)}"
                }
            
            return {
                "healthy": True,
                "message": "File permissions OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"File permissions check failed: {str(e)}"
            }


def main():
    """Main entry point for security setup utility."""
    parser = argparse.ArgumentParser(description="Setup NornFlow security system")
    parser.add_argument("--setup-secrets", action="store_true", help="Setup secrets management")
    parser.add_argument("--setup-rbac", action="store_true", help="Setup RBAC system")
    parser.add_argument("--create-admin-user", type=str, help="Create admin user with email")
    parser.add_argument("--test-providers", action="store_true", help="Test secrets providers")
    parser.add_argument("--check-security", action="store_true", help="Perform security health check")
    parser.add_argument("--create-config", action="store_true", help="Create security configuration file")
    parser.add_argument("--config", type=Path, help="Security configuration file path")
    parser.add_argument("--username", type=str, help="Username for admin user")
    parser.add_argument("--password", type=str, help="Password for admin user")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files")
    
    args = parser.parse_args()
    
    try:
        # Initialize setup manager
        setup = SecuritySetup(args.config)
        
        # Create configuration file
        if args.create_config:
            result = setup.create_config_file(args.force)
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Setup secrets management
        if args.setup_secrets:
            result = setup.setup_secrets_management()
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Setup RBAC system
        if args.setup_rbac:
            result = setup.setup_rbac_system()
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Create admin user
        if args.create_admin_user:
            result = setup.create_admin_user(
                email=args.create_admin_user,
                username=args.username,
                password=args.password
            )
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Test providers
        if args.test_providers:
            result = asyncio.run(setup.test_secrets_providers())
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Security health check
        if args.check_security:
            result = setup.check_security_health()
            print(json.dumps(result, indent=2))
            if not result["healthy"]:
                sys.exit(1)
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"Security setup operation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
