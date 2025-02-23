import asyncio
import httpx
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DeploymentChecker:
    def __init__(self):
        self.cloud_run_url = os.getenv('CLOUD_RUN_URL')
        if not self.cloud_run_url:
            raise ValueError("CLOUD_RUN_URL not found in environment variables")
        
        self.tokko_api_key = os.getenv('TOKKO_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
    async def check_health(self):
        """Check if the deployment is healthy"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.cloud_run_url}/health")
                return {
                    "status": response.status_code,
                    "response": response.json()
                }
            except Exception as e:
                logger.error(f"Health check failed: {str(e)}")
                return {"status": "error", "message": str(e)}

    async def test_chat(self, message: str):
        """Test the chat endpoint"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.cloud_run_url}/chat",
                    json={"message": message}
                )
                return response.json()
            except Exception as e:
                logger.error(f"Chat test failed: {str(e)}")
                return {"status": "error", "message": str(e)}

    async def check_tokko_connection(self):
        """Test the Tokko API connection"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.cloud_run_url}/api/properties",
                    headers={"Authorization": f"Bearer {self.tokko_api_key}"}
                )
                return response.json()
            except Exception as e:
                logger.error(f"Tokko API test failed: {str(e)}")
                return {"status": "error", "message": str(e)}

async def check_deployment():
    cloud_run_url = os.getenv('CLOUD_RUN_URL')
    if not cloud_run_url:
        print("Error: CLOUD_RUN_URL not found in environment variables")
        return

    async with httpx.AsyncClient() as client:
        try:
            # Check health endpoint
            response = await client.get(f"{cloud_run_url}/health")
            print(f"Health check status: {response.status_code}")
            print(f"Response: {response.json()}")

            # Test chat endpoint
            test_message = {
                "message": "Hola, busco departamento en Villa Ballester"
            }
            response = await client.post(f"{cloud_run_url}/chat", json=test_message)
            print(f"\nChat test status: {response.status_code}")
            print(f"Response: {response.json()}")

        except Exception as e:
            print(f"Error checking deployment: {str(e)}")

async def main():
    try:
        checker = DeploymentChecker()
        
        # Check basic health
        logger.info("Checking deployment health...")
        health = await checker.check_health()
        logger.info(f"Health check result: {health}")

        # Test chat functionality
        logger.info("\nTesting chat endpoint...")
        test_messages = [
            "Hola, busco departamento en Villa Ballester",
            "Quiero alquilar una casa",
            "¿Hay departamentos en venta?"
        ]
        
        for message in test_messages:
            logger.info(f"\nTesting message: {message}")
            result = await checker.test_chat(message)
            logger.info(f"Chat response: {result}")
            await asyncio.sleep(2)  # Add delay between requests

        # Check Tokko integration
        logger.info("\nTesting Tokko API integration...")
        tokko_result = await checker.check_tokko_connection()
        logger.info(f"Tokko API test result: {tokko_result}")

    except Exception as e:
        logger.error(f"Deployment check failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(check_deployment())