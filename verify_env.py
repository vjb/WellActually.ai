import asyncio
import logging
import os
import sys
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EnvVerifier")

async def test_anthropic(api_key: str) -> bool:
    logger.info("Testing Anthropic API connectivity...")
    if not api_key or api_key.startswith("sk-ant-mock"):
        logger.error("Anthropic API key is missing or is a placeholder.")
        return False
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                logger.info("✓ Anthropic API key is VALID.")
                return True
            else:
                logger.error(f"✗ Anthropic API check failed: HTTP {response.status_code} - {response.text.strip()}")
                return False
        except Exception as e:
            logger.exception(f"✗ Anthropic API request raised exception: {e}")
            return False

async def test_openai(api_key: str) -> bool:
    logger.info("Testing OpenAI API connectivity...")
    if not api_key or api_key.startswith("sk-proj-mock"):
        logger.error("OpenAI API key is missing or is a placeholder.")
        return False

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                logger.info("✓ OpenAI API key is VALID.")
                return True
            else:
                logger.error(f"✗ OpenAI API check failed: HTTP {response.status_code} - {response.text.strip()}")
                return False
        except Exception as e:
            logger.exception(f"✗ OpenAI API request raised exception: {e}")
            return False

async def test_github(token: str) -> bool:
    logger.info("Testing GitHub API connectivity...")
    if not token or token.startswith("ghp_mock"):
        logger.error("GitHub token is missing or is a placeholder.")
        return False

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Codeband-Swarm-Verifier",
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"✓ GitHub token is VALID. User: {user_data.get('login')}")
                return True
            else:
                logger.error(f"✗ GitHub token check failed: HTTP {response.status_code} - {response.text.strip()}")
                return False
        except Exception as e:
            logger.exception(f"✗ GitHub API request raised exception: {e}")
            return False

async def test_band(api_key: str, rest_url: str) -> bool:
    logger.info("Testing Band.ai API connectivity...")
    if not api_key or api_key.startswith("band_u_mock"):
        logger.error("Band.ai API key is missing or is a placeholder.")
        return False

    try:
        from thenvoi_rest import AsyncRestClient
        client = AsyncRestClient(api_key=api_key, base_url=rest_url)
        response = await client.human_api_profile.get_my_profile()
        
        if response and response.data:
            profile = response.data
            name = getattr(profile, 'name', 'N/A')
            email = getattr(profile, 'email', 'N/A')
            logger.info(f"✓ Band.ai API key is VALID. Profile Name: {name} (Email: {email})")
            return True
        else:
            logger.error("✗ Band.ai API key check failed: empty profile response.")
            return False
    except Exception as e:
        logger.exception(f"✗ Band.ai API connection raised exception: {e}")
        return False

async def test_aiml(api_key: str) -> bool:
    logger.info("Testing AIML API connectivity...")
    if not api_key:
        logger.error("AIML API key is missing.")
        return False

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.aimlapi.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                logger.info("✓ AIML API key is VALID.")
                return True
            else:
                logger.error(f"✗ AIML API check failed: HTTP {response.status_code} - {response.text.strip()}")
                return False
        except Exception as e:
            logger.exception(f"✗ AIML API request raised exception: {e}")
            return False

async def test_featherless(api_key: str) -> bool:
    logger.info("Testing Featherless API connectivity...")
    if not api_key:
        logger.error("Featherless API key is missing.")
        return False

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.featherless.ai/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=15.0,
            )
            if response.status_code == 200:
                logger.info("✓ Featherless API key is VALID.")
                return True
            else:
                logger.error(f"✗ Featherless API check failed: HTTP {response.status_code} - {response.text.strip()}")
                return False
        except Exception as e:
            logger.exception(f"✗ Featherless API request raised exception: {e}")
            return False


async def main():
    logger.info("Loading environment configuration...")
    # Load .env explicitly from the script's folder
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path)
    
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    band_key = os.environ.get("BAND_API_KEY")
    github_token = os.environ.get("GH_TOKEN")
    aiml_key = os.environ.get("AIML_API_KEY")
    featherless_key = os.environ.get("FEATHERLESS_API_KEY")
    
    # We read codeband.yaml to get the band.rest_url
    band_rest_url = "https://app.band.ai"
    try:
        import yaml
        config_path = Path(__file__).resolve().parent / "codeband.yaml"
        if config_path.is_file():
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                band_rest_url = cfg.get("band", {}).get("rest_url", band_rest_url)
    except Exception:
        pass
    
    results = {}
    
    # Run tests sequentially
    results["Anthropic"] = await test_anthropic(anthropic_key)
    print("-" * 60)
    results["OpenAI"] = await test_openai(openai_key)
    print("-" * 60)
    results["GitHub"] = await test_github(github_token)
    print("-" * 60)
    results["Band.ai"] = await test_band(band_key, band_rest_url)
    print("-" * 60)
    results["AIML API"] = await test_aiml(aiml_key)
    print("-" * 60)
    results["Featherless"] = await test_featherless(featherless_key)
    print("=" * 60)
    
    logger.info("VERIFICATION SUMMARY:")
    all_ok = True
    for service, status in results.items():
        status_str = "SUCCESS" if status else "FAILURE"
        logger.info(f"  {service.ljust(15)}: {status_str}")
        if not status:
            all_ok = False
            
    if all_ok:
        logger.info("All environment keys are successfully verified!")
        sys.exit(0)
    else:
        logger.error("Some environment keys failed verification.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
