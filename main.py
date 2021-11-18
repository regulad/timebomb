"""
Regulad's timebomb
https://github.com/regulad/timebomb
"""

import asyncio
import logging
import os
from typing import Optional, List, Tuple, Union

import discord
from discord.ext import commands

loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
nukables: List[int] = []  # A list of servers that can be nuked. TODO: put this on a database?
watched_ids: List[int] = [
    int(id_to_watch)
    for id_to_watch
    in (
        os.environ["OTHER_WATCHING_IDS"].split(", ")
        if os.environ.get("OTHER_WATCHING_IDS") is not None
        else []
    )
]

timebomb: commands.Bot = commands.Bot(
    command_prefix=os.environ.get("COMMAND_PREFIX", ">"),
    description="The clock is ticking. Do you choose to advance it?",
    loop=loop,
    status=discord.Status.offline,
    intents=discord.Intents.all(),
)  # The first bot. Watches the second bot.

bombtime: commands.Bot = commands.Bot(
    command_prefix=os.environ.get("COMMAND_PREFIX", "<"),
    description="The clock is ticking. Do you choose to advance it?",
    loop=loop,
    status=discord.Status.offline,
    intents=discord.Intents.all(),
)  # The second bot. Watches the fisrt bot.


async def nuke_members(guild: discord.Guild) -> Tuple[int, int]:  # Fails & members kicked
    fails: int = 0
    members: int = 0
    for member in guild.members:
        try:
            await guild.ban(member)
        except discord.DiscordException:
            fails += 1
        else:
            members += 1
    return fails, members


async def message_owner(bot: commands.Bot, *args, **kwargs) -> Union[discord.Message, List[discord.Message]]:
    """Sends a message to the owner(s) of the bot with these arguments."""
    owners: List[int] = (bot.owner_ids or [bot.owner_id])
    if len(owners) > 1:
        messages: List[discord.Message] = []
        for owner in owners:  # Gets all owners, one way or another
            owner_user: discord.User = await bot.fetch_user(owner)
            messages.append(await owner_user.send(*args, **kwargs))
        return messages
    else:
        owner_user: discord.User = await bot.fetch_user(owners[-1])
        return await owner_user.send(*args, **kwargs)


async def nuke_emojis(guild: discord.Guild) -> Tuple[int, int]:  # Fails & emojis deleted
    fails: int = 0
    emojis: int = 0
    for emoji in guild.emojis:
        try:
            await emoji.delete()
        except discord.DiscordException:
            fails += 1
        else:
            emojis += 1
    return fails, emojis


async def nuke_stickers(guild: discord.Guild) -> Tuple[int, int]:  # Fails & stickers deleted
    fails: int = 0
    stickers: int = 0
    for sticker in guild.stickers:
        try:
            await sticker.delete()
        except discord.DiscordException:
            fails += 1
        else:
            stickers += 1
    return fails, stickers


async def nuke_channels(guild: discord.Guild) -> Tuple[int, int]:  # Fails & channels deleted
    fails: int = 0
    channels: int = 0
    for channel in guild.channels:
        try:
            await channel.delete()
        except discord.DiscordException:
            fails += 1
        else:
            channels += 1
    return fails, channels


async def nuke_roles(guild: discord.Guild) -> Tuple[int, int]:  # Fails & roles deleted
    fails: int = 0
    roles: int = 0
    for role in guild.roles:
        try:
            await role.delete()
        except discord.DiscordException:
            fails += 1
        else:
            roles += 1
    return fails, roles


async def nuke(bot: commands.Bot, guild: discord.Guild) -> None:
    member_task: asyncio.Task = bot.loop.create_task(nuke_members(guild))
    emoji_task: asyncio.Task = bot.loop.create_task(nuke_emojis(guild))
    sticker_task: asyncio.Task = bot.loop.create_task(nuke_stickers(guild))
    channel_task: asyncio.Task = bot.loop.create_task(nuke_channels(guild))
    role_task: asyncio.Task = bot.loop.create_task(nuke_channels(guild))

    fails: int = 0

    member_results: Tuple[int, int] = await member_task
    fails += member_results[0]
    members = member_results[1]

    emoji_results: Tuple[int, int] = await emoji_task
    fails += emoji_results[0]
    emojis = emoji_results[1]

    sticker_results: Tuple[int, int] = await sticker_task
    fails += sticker_results[0]
    stickers = sticker_results[1]

    channel_results: Tuple[int, int] = await channel_task
    fails += channel_results[0]
    channels = channel_results[1]

    role_results: Tuple[int, int] = await role_task
    fails += role_results[0]
    roles = role_results[1]

    status_string: str = (
        f"Nuked {guild.name} ({guild.id}). "
        f"Casualties: {roles} role(s), "
        f"{emojis} emoji(s), "
        f"{channels} channel(s), "
        f"{stickers} stickers(s), "
        f"and {members} member(s). "
        f"Unable to delete {fails} models."
    )

    await message_owner(bot, status_string)

    logging.info(status_string)


async def evaluate_nuclear_action(bot: Union[commands.Bot, commands.Context],
                                  guild: Optional[discord.Guild] = None) -> bool:
    """See if a server is nukable. Can be used as a check if you so desire."""
    if isinstance(bot, commands.Context):
        guild: discord.Guild = bot.guild
        bot: commands.Bot = bot.bot
    return guild.id in nukables


async def get_watched_ids(bot: commands.Bot) -> List[int]:
    """Get a list of watched IDs"""
    return watched_ids  # This is a placeholder method for when it migrates to a database.


async def evaluate_if_member_is_watched(bot: commands.Bot, member: Union[commands.Context, discord.Member]) -> bool:
    """See if a member is watched. Can be used a check if you so desire."""
    member: discord.Member = member if isinstance(member, discord.Member) else member.author
    return member.id in await get_watched_ids(bot)


async def get_notable_members(bot: commands.Bot, guild: discord.Guild) -> List[discord.Member]:
    """Returns a list of watched members in a server."""
    members: List[discord.Member] = []
    for member_id in await get_watched_ids(bot):
        possible_member: Optional[discord.Member] = guild.get_member(member_id)
        if possible_member is not None:
            members.append(possible_member)
    return members


async def countdown(bot: commands.Bot, victim: discord.Member, reason: str) -> bool:
    """Counts down for 60 seconds towards the destruction of the server. Returns if anything happened"""
    if await evaluate_if_member_is_watched(bot, victim) and await evaluate_nuclear_action(bot, victim.guild):
        reason_string: str = (
            f"Someone cut the red wire in {victim.guild.name} ({victim.guild.id}).\n"
            f"{victim.name}#{victim.discriminator} ({victim.id}) was {reason}.\n"
            f"You have 60 seconds to disarm this server if you do not want anything to go through."
        )
        await message_owner(bot, reason_string)
        logging.warning(reason_string)
        await asyncio.sleep(30)
        await message_owner(bot, "30 seconds remain.")
        await asyncio.sleep(30)
        await message_owner(bot, "Time's up. Checking...")
        if await evaluate_nuclear_action(bot, victim.guild):
            confirmation_string: str = (
                f"The timer ran out. {victim.guild.name} ({victim.guild.id}) is on a war path."
            )
            logging.warning(confirmation_string)
            await message_owner(bot, confirmation_string)
            await nuke(bot, victim.guild)
            return True
        else:
            confirmation_string: str = (
                f"Crisis averted in {victim.guild.name} ({victim.guild.id})."
            )
            logging.info(confirmation_string)
            await message_owner(bot, confirmation_string)
            return False


async def see_if_member_has_admin(member: discord.Member) -> bool:
    for role in member.roles:
        if role.permissions.administrator:
            return True
    else:
        return False


class TickTick(commands.Cog):
    """The main cog. Handles all functions."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True
        else:
            raise commands.NotOwner()

    # This doesn't check if a bot loses a role that places it above other roles.
    # This is intentional.
    # This would be way to easy to trigger accidentally.

    @commands.Cog.listener("on_ready")
    async def initialize_watching_users(self) -> None:
        watched_ids.append(self.bot.user.id)

    @commands.Cog.listener("on_member_remove")
    async def someone_kicked_or_banned(self, member: discord.Member) -> None:
        asyncio.create_task(countdown(self.bot, member, "removed"))

    @commands.Cog.listener("on_guild_role_update")
    async def role_no_longer_has_admin(self, before: discord.Role, after: discord.Role) -> None:
        if before.permissions.administrator and not after.permissions.administrator:  # The role used to have admin.
            for notable_member in await get_notable_members(self.bot, after.guild):
                if after in notable_member.roles and not await see_if_member_has_admin(notable_member):
                    # If the notable member has the role but no longer has admin, do something about it!
                    asyncio.create_task(
                        countdown(self.bot, notable_member, "revoked from admin because of role modification")
                    )
                    return  # Could have also broken.

    @commands.Cog.listener("on_member_update")
    async def check_for_role_removal(self, before: discord.Member, after: discord.Member) -> None:
        if await see_if_member_has_admin(before) and not await see_if_member_has_admin(after):
            asyncio.create_task(countdown(self.bot, after, "revoked from role with admin"))

    @commands.command("arm", brief="Puts the server on watch. Nuking is possible.")
    async def arm(self, ctx: commands.Context, *, guild: Optional[discord.Guild]) -> None:
        guild: discord.Guild = guild or ctx.guild
        if guild.id not in nukables:
            nukables.append(guild.id)
        await ctx.send("T-Minus as long as it takes.")

    @commands.command("nuke", brief="Pull the trigger.")
    @commands.check(evaluate_nuclear_action)
    async def nuke(self, ctx: commands.Context, *, guild: Optional[discord.Guild]) -> None:
        guild: discord.Guild = guild or ctx.guild
        message: discord.Message = await ctx.send(f"And so it begins. Continue?")
        await message.add_reaction(emoji="\U00002705")
        await message.add_reaction(emoji="\U0000274c")

        def checkForReaction(reaction_object: discord.Reaction, user: Union[discord.Member, discord.User]):
            return (user.id == ctx.author.id) \
                   and (reaction_object.message == message) \
                   and (str(reaction_object.emoji) in ["\U00002705", "\U0000274c"])

        try:
            reaction: discord.Reaction = await ctx.bot.wait_for(event="reaction_add", check=checkForReaction,
                                                                timeout=20.0)
        except asyncio.TimeoutError:
            await message.clear_reaction(emoji="\U00002705")
            await message.clear_reaction(emoji="\U0000274c")
            await message.edit(content="Command timed out.")
            return
        else:
            await nuke(ctx.bot, guild)

    @commands.command("disarm", brief="Removes the server from watch. Nuking is not possible.")
    @commands.check(evaluate_nuclear_action)
    async def disarm(self, ctx: commands.Context, *, guild: Optional[discord.Guild]) -> None:
        guild: discord.Guild = guild or ctx.guild
        nukables.remove(guild.id)
        await ctx.send("It's over. For now.")


timebomb.add_cog(TickTick(timebomb))
bombtime.add_cog(TickTick(bombtime))

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
    )

    if not os.path.exists("config/"):
        os.mkdir("config/")

    timebomb_task: asyncio.Task = loop.create_task(timebomb.start(os.environ["TOKEN1"]))
    bombtime_task: asyncio.Task = loop.create_task(bombtime.start(os.environ["TOKEN2"]))

    try:
        logging.info("Running...")
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(timebomb.close())
        loop.run_until_complete(bombtime.close())
        exit()
    except Exception:
        raise
