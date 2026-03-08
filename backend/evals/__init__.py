from pathlib import Path
import dotenv
import logfire

dotenv.load_dotenv(Path(__file__).parent.parent / ".env")
logfire.configure(send_to_logfire="if-token-present")
