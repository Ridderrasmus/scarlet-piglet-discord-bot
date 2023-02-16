from discordbot import *
import multiprocessing
import os

def main():
    # Run the bot
    BOT.run(os.getenv('DISCORD_TOKEN'))
    

if __name__ == "__main__":
    main()
