from server.server import run
from logging import basicConfig, DEBUG

basicConfig(level=DEBUG)

if __name__ == "__main__":
    run()