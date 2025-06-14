import requests
from typing import Optional, Dict, Any
from app.core.config import settings


class OTPLESSService:
    """Service for handling OTPLESS authentication and token verification"""
    
    def __init__(self):
        # Use correct API endpoint per official documentation
        self.api_base_url = "https://user-auth.otpless.app"
        self.client_id = settings.otpless_client_id
        self.client_secret = settings.otpless_client_secret
        self.app_id = settings.otpless_app_id
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify OTPLESS token and extract user information
        Following official docs: https://otpless.com/docs/api-reference/endpoint/verifytoken/verify-token-with-secure-data
        
        Args:
            token (str): OTPLESS authentication token
            
        Returns:
            Dict[str, Any]: User information if token is valid, None otherwise
        """
        try:
            # Headers as per official documentation
            headers = {
                "Content-Type": "application/json",
                "clientId": self.client_id,
                "clientSecret": self.client_secret
            }
            
            payload = {
                "token": token
            }
            
            print(f"🔍 OTPLESS Token Verification Request:")
            print(f"  - URL: {self.api_base_url}/auth/v1/validate/token")
            print(f"  - Headers: {headers}")
            print(f"  - Payload: {payload}")
            
            # Use correct endpoint per official documentation
            response = requests.post(
                f"{self.api_base_url}/auth/v1/validate/token",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            print(f"📡 OTPLESS API Response:")
            print(f"  - Status Code: {response.status_code}")
            print(f"  - Response Text: {response.text}")
            
            if response.status_code == 200:
                user_data = response.json()
                
                print(f"✅ OTPLESS Response JSON: {user_data}")
                
                # Check response status per official documentation format
                if user_data.get("status") == "SUCCESS":
                    return self._extract_user_info(user_data)
                else:
                    print(f"❌ OTPLESS verification failed: {user_data.get('message', 'Unknown error')}")
                    return None
                    
            else:
                print(f"❌ OTPLESS API error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"❌ Network error during OTPLESS verification: {str(e)}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error during OTPLESS verification: {str(e)}")
            return None
    
    def _extract_user_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize user information from OTPLESS response
        Following official response structure
        
        Args:
            data (Dict[str, Any]): Raw OTPLESS user data
            
        Returns:
            Dict[str, Any]: Normalized user information
        """
        # Extract identities from official response structure
        identities = data.get("identities", [])
        
        # Initialize user info
        user_info = {
            "otpless_user_id": data.get("userId"),
            "mobile": None,
            "email": None,
            "name": None,
            "profile_picture": None,
            "auth_provider": "otpless",
            "verified": False
        }
        
        print(f"🔍 Processing identities: {identities}")
        
        # Process identities to extract user data
        for identity in identities:
            identity_type = identity.get("identityType", "").upper()
            identity_value = identity.get("identityValue")
            is_verified = identity.get("verified", False)
            
            print(f"  - Identity: {identity_type} = {identity_value}, verified: {is_verified}")
            
            if identity_type == "MOBILE" and identity_value:
                print(f"📱 === OTPLESS MOBILE EXTRACTION DEBUG ===")
                print(f"📱 Raw mobile from OTPLESS: '{identity_value}'")
                print(f"📱 Mobile type: {type(identity_value)}")
                print(f"📱 Mobile length: {len(identity_value)}")
                print(f"📱 Mobile repr: {repr(identity_value)}")
                print(f"📱 Mobile starts with +: {identity_value.startswith('+') if identity_value else False}")
                print(f"📱 Mobile starts with +91: {identity_value.startswith('+91') if identity_value else False}")
                print(f"📱 Mobile is verified: {is_verified}")
                print(f"📱 =======================================")
                
                user_info["mobile"] = identity_value
                user_info["auth_provider"] = "otpless_mobile"
                if is_verified:
                    user_info["verified"] = True
                    
            elif identity_type == "EMAIL" and identity_value:
                user_info["email"] = identity_value
                if user_info["auth_provider"] == "otpless":
                    user_info["auth_provider"] = "otpless_email"
                if is_verified:
                    user_info["verified"] = True
                    
            # Extract name from identity
            if identity.get("name"):
                user_info["name"] = identity.get("name")
        
        # Handle social login data
        if identities:
            first_identity = identities[0]
            methods = first_identity.get("methods", [])
            
            print(f"🔍 Authentication methods: {methods}")
            
            if "GOOGLE" in methods:
                user_info["auth_provider"] = "otpless_google"
            elif "FACEBOOK" in methods:
                user_info["auth_provider"] = "otpless_facebook"
            elif "APPLE" in methods:
                user_info["auth_provider"] = "otpless_apple"
            elif "TRUE_CALLER" in methods:
                user_info["auth_provider"] = "otpless_truecaller"
        
        print(f"✅ Extracted user info: {user_info}")
        return user_info
    
    def get_auth_providers(self) -> list:
        """
        Get available authentication providers
        
        Returns:
            list: Available authentication providers
        """
        return [
            "otpless_mobile",
            "otpless_email", 
            "otpless_google",
            "otpless_facebook",
            "otpless_apple",
            "otpless_truecaller"
        ]


# Create singleton instance
otpless_service = OTPLESSService() 