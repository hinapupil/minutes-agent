from __future__ import annotations

import discord
from discord.ext import commands

from minutes_agent.api_client import AgentApiClient
from minutes_agent.config import Settings


class AskCog(commands.Cog):
    def __init__(self, settings: Settings) -> None:
        self._client = AgentApiClient(settings)

    @discord.slash_command(name="ask", description="過去の議事録に関する質問をします")
    async def ask(self, ctx: discord.ApplicationContext, question: str) -> None:
        await ctx.defer(ephemeral=False)
        try:
            response = self._client.post("/commands/ask", {"question": question})
            await ctx.followup.send(response.get("answer", "回答が空です"))
        except Exception as exc:
            await ctx.followup.send(f"質問処理に失敗しました: {exc}", ephemeral=True)

