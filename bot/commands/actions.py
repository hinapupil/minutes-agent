from __future__ import annotations

import discord
from discord.ext import commands

from minutes_agent.api_client import AgentApiClient
from minutes_agent.config import Settings


class ActionsCog(commands.Cog):
    def __init__(self, settings: Settings) -> None:
        self._client = AgentApiClient(settings)

    @discord.slash_command(name="actions", description="アクションアイテムを表示します")
    @discord.option(
        "status",
        str,
        description="open / in_progress / completed",
        required=False,
        choices=["open", "in_progress", "completed"],
    )
    async def actions(self, ctx: discord.ApplicationContext, status: str | None = None) -> None:
        await ctx.defer(ephemeral=True)
        try:
            response = self._client.post("/commands/actions", {"status": status})
            actions = response.get("actions", [])
            await ctx.followup.send(_format_actions(actions), ephemeral=True)
        except Exception as exc:
            await ctx.followup.send(f"アクション一覧の取得に失敗しました: {exc}", ephemeral=True)

    @discord.slash_command(name="action-done", description="アクションアイテムを完了にします")
    @discord.option("id", str, description="Action item ID")
    async def action_done(self, ctx: discord.ApplicationContext, id: str) -> None:
        await ctx.defer(ephemeral=True)
        try:
            response = self._client.post("/commands/action-done", {"action_id": id})
            action = response.get("action", {})
            title = action.get("title", id)
            await ctx.followup.send(f"`{id}` {title} を完了にしました", ephemeral=True)
        except Exception as exc:
            await ctx.followup.send(f"完了処理に失敗しました: {exc}", ephemeral=True)


def _format_actions(actions: object) -> str:
    if not isinstance(actions, list) or not actions:
        return "該当するアクションアイテムはありません"
    lines = ["アクションアイテム"]
    for item in actions:
        if not isinstance(item, dict):
            continue
        due = item.get("due_date") or "期限未設定"
        assignee = item.get("assignee") or "担当者未設定"
        action_id = item.get("action_id") or "-"
        title = item.get("title") or "(no title)"
        status = item.get("status") or "-"
        lines.append(f"- `{action_id}` {title} / {status} / {assignee} / {due}")
    return "\n".join(lines)

