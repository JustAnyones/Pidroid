# Pidroid

Pidroid is a custom discord bot for TheoTown written in Python using Rapptz's [discord.py](https://github.com/Rapptz/discord.py) wrapper.

This project contains multiple packages prefixed with `pidroid-`. Each package contains its own documentation.


## Structure

This is a work in progress on how to structure the repository.

- Projects that are considered as a shared package shall be placed under `packages/pidroid-PKG`.
    - For example, `pidroid-core`, `pidroid-ipc`
- Projects that are considered standalone runnables such as the bot that connects to Discord,
  the api, other services are to be placed under `services/RUNNABLE`.
    - For example, `services/bot`, `services/api`, `services/ai`.
- The frontend is not inherently much of a runnable and is static content that shall be served by
  a web host. That could just be stored at root under `/web`.
