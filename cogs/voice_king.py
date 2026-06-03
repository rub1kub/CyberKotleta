"""
Недельный титул Войс-царя.

Роль выдаётся участнику с максимальным временем в голосовых каналах за текущую неделю.
При захвате трона бот публично объявляет смену лидера.
"""

import logging
import random
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from db.database import Database
from utils.formatting import format_time_seconds

logger = logging.getLogger(__name__)


CAPTURE_TEMPLATES = [
    "🎙 **ТРОН ЗАХВАЧЕН.** {new} выбил {old} из кресла Войс-царя. {old}, можешь пока погреть лавку запасных.",
    "👑 {new} забрал титул **Войс-царя**. {old}, твоя эпоха закончилась быстрее, чем оправдания после лива из войса.",
    "💀 {old} больше не Войс-царь. {new} прошёл мимо, забрал корону и оставил табличку «не мешать профессионалам».",
    "📉 {old} потерял трон. {new} теперь главный по войсу, а бывший царь официально переведён в массовку.",
    "🔥 {new} снёс {old} с вершины войса. Просим не плакать в микрофон — статистика слёз не учитывается.",
    "🪑 {old} слетел с трона так быстро, будто стул был из ИКЕИ после третьего переезда. {new} теперь сидит сверху.",
    "🧹 {new} подмёл {old} из войс-истории. Остался только пыльный след и запах проёбанного титула.",
    "⚰️ {old}, статистика заказала тебе маленький деревянный рейтинг. {new} уже читает некролог Войс-царя.",
    "📦 {old} упакован в коробку «бывший царь». {new} забрал корону и даже скотч не попросил.",
    "🗿 {new} поставил {old} памятник из позора. На табличке написано: «сидел много, но недостаточно».",
    "🥀 {old} завял как цветок на подоконнике сервера. {new} полил трон бензином и поджёг интригу.",
    "🧯 Пожарная тревога: {new} сжёг рекорд {old}. Не паникуйте, это просто чья-то корона превратилась в пепел.",
    "🔨 {new} забил последний гвоздь в табличку «{old} был царём». Получилось криво, но по делу.",
    "🪦 На серверном кладбище появилась новая плита: «{old}, царствовал недолго, проебал красиво». {new} несёт венок.",
    "💅 {new} забрал трон без суеты. {old}, это был не камбэк, это был рекламный ролик поражения.",
    "🧃 {old} выжат из титула как дешёвый пакетик сока. {new} пьёт статистику через трубочку.",
    "🎪 {old} завершил цирковое выступление. {new} выходит на арену, клоунам просьба освободить трон.",
    "🧊 {new} заморозил {old} в таблице лидеров. Разморозка платная, уважение не включено.",
    "🍽️ {new} съел отрыв {old} без соли. На десерт — чужая корона и тишина в ответ.",
    "🚬 {old} докурил своё царство до фильтра. {new} забрал трон, пепельницу и остатки достоинства.",
    "🐀 {old} покинул трон через служебный выход. {new} вошёл через парадный и громко хлопнул статистикой.",
    "🧻 {new} использовал прошлое лидерство {old} как черновик. Итоговый вариант теперь у него.",
    "📉 Акции {old} рухнули. {new} провёл враждебное поглощение трона и оставил миноритариев ныть.",
    "🪓 {new} отрубил {old} от короны. Не хирургия, конечно, но пациентом сервер доволен.",
    "🧨 {old} взорвался на ровном месте рейтинга. {new} просто стоял рядом с часами и улыбался.",
    "🕳️ {old} провалился в яму под названием «недостаточно сидел». {new} поставил сверху табличку «не прыгать».",
    "🥶 {new} забрал трон холодно и без объяснений. {old}, тебе даже проигрыш не прогрели.",
    "📺 {old} был сериалом на один сезон. {new} получил продление, бюджет и нормальный сценарий.",
    "🏚️ Царство {old} признано аварийным. {new} уже делает ремонт, выносит мусор и старую корону.",
    "🧛 {new} высосал лидерство из {old}. Осталась оболочка, пара часов и тяжёлый серверный вздох.",
    "🪤 {old} попался в ловушку собственной самоуверенности. {new} забрал сыр, трон и уважение.",
    "🚽 {old} смыт из истории Войс-царя. {new} нажал кнопку два раза, чтобы наверняка.",
    "🥊 {new} отправил {old} в статистический нокдаун. Судья даже считать не стал — и так всё понятно.",
    "🧟 {old} ещё ходит, но титул уже мёртв. {new} забрал корону с холодного рейтингового трупа.",
    "🧾 Счёт выставлен: {old} задолжал серверу один трон. {new} оплатил часами и забрал сдачу.",
    "🐌 {old} ехал к победе на улитке. {new} пришёл пешком и всё равно обогнал.",
    "🧠 {old} пытался думать, что он царь. {new} показал таблицу, и мысль умерла первой.",
    "💣 {new} кинул в рейтинг гранату из часов. {old} нашёл только свои амбиции по кускам.",
    "🪙 {old} был царём на сдачу. {new} зашёл с крупной купюрой и купил весь трон.",
    "🧼 {new} отмыл трон от следов {old}. Грязь сошла, легенда — тоже.",
    "📌 {old} приколот к доске позора. {new} подписал маркером: «тут был бывший».",
    "🫠 {old} растаял под давлением часов. {new} просто не выключал войс и включил доминацию.",
    "🚜 {new} переехал {old} трактором статистики. Асфальт ровный, самооценка бывшего — нет.",
    "🧱 {old} ударился об стену реальности. На стене было написано: «{new} сидел дольше».",
    "🦴 {new} оставил от царства {old} только косточку для археологов сервера.",
    "🛒 {old} выехал из трона в тележке для скидочного товара. {new} забрал премиум-полку.",
    "📞 {old}, тебе звонили из прошлого — просили вернуть корону, там она хотя бы смотрелась.",
    "🧂 {new} посолил рану {old} свежими часами. Больно? Зато по таблице честно.",
    "🏴‍☠️ {new} взял трон абордажем. {old} утонул в собственном «я ещё вернусь».",
    "🧯 {old} горит в рейтинге, но тушить никто не будет. {new} экономит воду для победителей.",
    "🔪 {new} нарезал отрыв {old} тонкими ломтиками. Подача холодная, унижение свежее.",
    "🧑‍⚖️ Суд сервера постановил: {old} виновен в недостаточном царствовании. {new} получает трон без апелляции.",
    "🏁 {old} финишировал вторым в гонке, где был один победитель. {new} забрал кубок и микрофон.",
    "🧳 {old}, собирай манатки. {new} уже переехал на трон и сменил замки.",
    "🧪 Эксперимент завершён: {old} не выдержал дозу конкуренции. {new} признан стабильным царём.",
    "🪫 {old} сел как старый аккумулятор. {new} подключился к розетке понтов и зарядил трон.",
    "🦷 {new} вырвал титул у {old} без анестезии. Стоматология рейтинга сегодня бесплатная.",
    "🧯 {old} просил не раздувать. {new} раздул, сжёг и поставил мангал на троне.",
    "📚 История запомнит {old} как сноску. {new} теперь целая глава, сука, с иллюстрациями.",
    "🧊 {old} отправлен в морозилку бывших царей. {new} подписал контейнер: «не размораживать».",
    "🎲 {old} кинул кубик и выпало «проебал». {new} даже не играл — просто насидел.",
    "🧨 {new} устроил рейтинговый хлопок. {old} думал, что это фейерверк, но это был конец эпохи.",
    "🪰 {old} жужжал про величие. {new} хлопнул статистикой, и в комнате стало тише.",
    "🦍 {new} зашёл на трон как хозяин качалки. {old} остался держать бутылочку с водой.",
    "🧟‍♂️ {old} пытался воскресить царство, но серверный некромант занят. {new} уже правит живыми.",
    "🧨 {old} сам себя заминировал ожиданиями. {new} просто наступил на кнопку.",
    "🪄 {new} сделал фокус: был {old} с короной, стал {old} без короны. Магия? Нет, часы.",
    "🫡 {old}, спасибо за службу. Можешь идти нахуй в резерв. {new} принимает командование.",
    "🦀 {old} пятился к поражению, но сделал вид, что это стратегия. {new} забрал трон без панциря.",
    "🚑 {old} увезён с диагнозом «острая нехватка часов». {new} прописан как главный раздражитель.",
    "🌚 {new} устроил тёмную ночь для царства {old}. Утро не обещаем.",
    "🪦 {old} умер как царь, но воскрес как мем. {new} поставил лайк на могилу рейтинга.",
    "💼 {old} уволен с должности Войс-царя за низкую производительность. {new} принят без испытательного срока.",
    "🥔 {old} превратился в гарнир к победе {new}. Подача горячая, достоинство пережарено.",
    "🚪 {new} открыл дверь в тронный зал ногой. {old} вышел тихо, чтобы не позориться громче.",
    "🕯️ За царство {old} поставили свечку. {new} задул её, потому что экономия кислорода.",
    "🧯 {new} затушил последние искры величия {old}. Остался дым, пепел и неловкая тишина.",
    "🧃 {old} был разбавленным царём. {new} принёс концентрат и сделал серверу крепко.",
    "🦴 {new} отобрал трон у {old} так чисто, что криминалисты нашли только стыд.",
    "🪦 {old} официально занесён в Красную книгу бывших царей. {new} охранять не будет.",
    "💀 {new} похоронил лидерство {old} без церемоний. Земля пухом, рейтинг — бетоном.",
    "🏆 {new} забрал кубок, трон и право издеваться. {old} забрал опыт и неприятный осадок.",
    "🪚 {old} был отпилен от трона ровно по линии позора. {new} держит инструмент и улыбается.",
    "🧻 {new} закрыл эпоху {old} одним движением. Бумаги ушло мало, унижения хватило всем.",
    "🔥 {old} сгорел на работе Войс-царя. {new} пришёл на смену и даже каску не надел.",
    "🧬 Анализ ДНК показал: у {old} нет гена царя. У {new} он, сука, доминантный.",
    "🛎️ {new} нажал кнопку сервиса, и {old} вынесли из тронного зала как пустую тарелку.",
    "🧱 {old} строил легенду из картона. {new} дунул часами — и всё нахер сложилось.",
    "⚱️ Прах царства {old} развеян по голосовым каналам. {new} попросил не мусорить на троне.",
    "🧯 {old} пытался быть огнём, но оказался дымком. {new} теперь пожар, блять, с сиреной.",
    "🪩 {new} включил дискотеку на костях лидерства {old}. Танцпол открыт, самооценка закрыта.",
]

FIRST_CORONATION_TEMPLATES = [
    "🎙 {new} стал **Войс-царём недели**. Остальные пока изображают декоративный шум в канале.",
    "👑 На троне войса теперь {new}. Если кто-то против — статистика ждёт, рот не считается.",
    "🔥 {new} забрал первый титул **Войс-царя** на этой неделе. Остальным пора перестать быть фоном.",
    "💀 {new} первым сел на трон недели. Сервер официально получил повод завидовать молча.",
    "🪑 {new} занял кресло Войс-царя. Остальные могут постоять — всё равно не насидели.",
    "📢 Внимание, сервер: {new} теперь Войс-царь. Ваши жалобы принимаются в мусорку.",
    "⚰️ {new} открыл неделю так, будто уже приготовил кладбище для чужих амбиций.",
    "🎪 {new} первый на троне. Цирк начинается, клоуны подтягиваются по расписанию.",
    "🧃 {new} выжал из недели первый титул. Остальные пока разбавляют присутствие водой.",
    "🧯 {new} загорелся в рейтинге. Не тушить — это редкий случай полезного пожара.",
    "🧠 {new} понял простую вещь: сидишь в войсе — получаешь корону. Гениально, сука.",
    "🏴‍☠️ {new} поднял флаг на троне. Абонемент на зависть для остальных уже активирован.",
    "🥶 {new} холодно забрал старт недели. Остальные пока размораживают оправдания.",
    "🧨 {new} взорвал начало недели и сел на трон. Обломки чужих планов убирать не будет.",
    "📦 {new} забрал титул из коробки «первый нахер успел». Доставка без возврата.",
    "🚬 {new} прикурил от первой короны недели. Пепел понтов уже летит по серверу.",
    "🪦 {new} поставил первую плиту на кладбище чужих надежд. Неделя обещает быть мерзкой.",
    "🧼 {new} отмыл трон до блеска и сразу испачкал его своим превосходством.",
    "🦍 {new} зашёл на трон без стука. Видимо, дверь сама поняла, кто тут главный.",
    "💼 {new} принят на должность Войс-царя недели. KPI: бесить всех присутствием.",
    "🧾 {new} выставил счёт серверу: уважение, зависть, часики. Оплата по факту унижения.",
    "🏚️ {new} занял трон до того, как остальные нашли вход в здание.",
    "🕯️ {new} зажёг свечу первой коронации. Не романтика — просто поминки по конкуренции.",
    "🧱 {new} положил первый кирпич в стену понтов. Остальные уже упёрлись лицом.",
    "🦷 {new} вцепился в трон зубами. Отдирать будут только вместе с рейтингом.",
    "🐌 {new} стал первым, пока остальные ползли к кнопке подключения.",
    "🧪 {new} доказал лабораторно: сидение в войсе вызывает корону и раздражение окружающих.",
    "🪙 {new} кинул монетку, и выпал трон. У остальных монетка упала в говно.",
    "🧊 {new} заморозил старт недели за собой. Разморозка конкурентов не планируется.",
    "🚜 {new} проехался по пустому рейтингу и назвал это началом царства.",
    "📺 Новый сезон начался: {new} в главной роли, остальные — массовка без реплик.",
    "🧟 {new} воскресил войс-гонку. Теперь сервер будет страдать, но с таблицей.",
    "🪄 {new} сделал первый фокус недели: появился в войсе и стал проблемой для всех.",
    "🥔 {new} сел на трон. Остальные пока в режиме картошки с микрофоном.",
    "🧂 {new} посолил начало недели понтами. На вкус неприятно, зато честно.",
    "🏆 {new} взял первую корону. Остальные могут потрогать воздух вокруг неё.",
    "🪫 {new} зарядил неделю своим присутствием. У конкурентов батарейка уже плачет.",
    "🧯 {new} объявлен первым пожаром недели. Паники нет, только токсичный дым.",
    "🪰 {new} стал царём, а вокруг уже жужжат будущие оправдания.",
    "⚱️ {new} первым занял трон и заранее заказал урны для чужих надежд.",
    "🛎️ {new} позвонил в колокол коронации. Сервер услышал и сделал вид, что ему не больно.",
    "🌚 {new} открыл тёмную неделю войса. Свет выключен, понты включены.",
    "🧬 У {new} обнаружен ген Войс-царя. У остальных пока только ген «потом зайду».",
    "🚪 {new} вошёл в тронный зал первым. Остальные стучатся в дверь статистики.",
    "🪩 {new} устроил вечеринку первой короны. Вход для конкурентов — через унижение.",
]


class VoiceKingCog(commands.Cog):
    """Ког для недельного Войс-царя."""

    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        self.last_announced_leaders: dict[int, int] = {}
        self.sync_voice_king_loop.start()

    def cog_unload(self):
        self.sync_voice_king_loop.cancel()

    def _get_target_guilds(self) -> list[discord.Guild]:
        if config.GUILD_ID:
            guild = self.bot.get_guild(config.GUILD_ID)
            return [guild] if guild else []
        return list(self.bot.guilds)

    def _find_voice_king_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        role = discord.utils.get(guild.roles, name=config.VOICE_KING_ROLE_NAME)
        if role:
            return role

        known_prefixes = [
            f"{config.VOICE_KING_ROLE_NAME} — ",
            "🎙 Войс-царь — ",
        ]
        known_exact_names = [
            config.VOICE_KING_ROLE_NAME,
            "🎙 Войс-царь",
        ]

        return next(
            (
                role
                for role in guild.roles
                if role.name in known_exact_names
                or any(role.name.startswith(prefix) for prefix in known_prefixes)
            ),
            None,
        )

    def _get_current_role_holders(self, guild: discord.Guild, role: discord.Role) -> list[discord.Member]:
        return [member for member in guild.members if role in member.roles and not member.bot]

    def _iter_live_voice_members(self, guild: discord.Guild) -> list[discord.Member]:
        """Получить всех живых участников в обычных голосовых каналах."""
        members = []
        seen_member_ids = set()

        for channel in guild.voice_channels:
            if channel == guild.afk_channel:
                continue

            for member in channel.members:
                if member.bot or member.id in seen_member_ids:
                    continue

                seen_member_ids.add(member.id)
                members.append(member)

        return members

    def _member_is_online(self, member: discord.Member) -> bool:
        """Проверить, видит ли бот участника онлайн."""
        return member.status != discord.Status.offline

    def _display_name(self, member: discord.Member) -> str:
        """Получить ник участника без возможности пинга."""
        return discord.utils.escape_mentions(member.display_name)

    async def _get_live_weekly_seconds(self, member: discord.Member, now: datetime) -> int:
        """Получить недельное время с учётом текущего несохранённого отрезка в войсе."""
        weekly_seconds = await self.db.get_weekly_voice_seconds(member.id)
        _, last_join_ts = await self.db.get_voice_stats(member.id)

        if not last_join_ts:
            return weekly_seconds

        active_seconds = max(0, int((now - last_join_ts).total_seconds()))
        return weekly_seconds + active_seconds

    async def _get_weekly_top_members(
        self,
        guild: discord.Guild,
        limit: int = 1000,
        online_only: bool = False,
    ) -> list[tuple[discord.Member, int]]:
        """Получить недельных лидеров среди участников сервера."""
        top = []
        for user_id, seconds in await self.db.get_top_weekly_voice(limit):
            member = guild.get_member(user_id)
            if member and not member.bot and (not online_only or self._member_is_online(member)):
                top.append((member, seconds))

        top.sort(key=lambda item: (-item[1], item[0].display_name.casefold(), item[0].id))
        return top

    def _build_role_name(self, seconds: Optional[int] = None) -> str:
        """Собрать название роли Войс-царя."""
        if seconds is None:
            return config.VOICE_KING_ROLE_NAME

        if seconds < 3600:
            minutes = max(1, seconds // 60)
            duration = f"{minutes}мин"
        else:
            duration = f"{seconds // 3600}ч"

        return f"{config.VOICE_KING_ROLE_NAME} — {duration}"[:100]

    async def _sync_role_name(self, role: discord.Role, seconds: Optional[int]) -> None:
        """Обновить название роли с текущими часами лидера."""
        target_name = self._build_role_name(seconds)
        if role.name == target_name:
            return

        try:
            await role.edit(name=target_name, reason="Обновление времени Войс-царя в названии роли")
            logger.info(f"Роль Войс-царя переименована: {target_name}")
        except discord.Forbidden:
            logger.error(f"Нет прав для переименования роли {role.name} ({role.id})")
        except discord.HTTPException as e:
            logger.error(f"Ошибка Discord API при переименовании роли {role.name}: {e}")

    async def ensure_voice_king_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Создать или обновить роль Войс-царя."""
        role = self._find_voice_king_role(guild)
        role_color = discord.Color(config.VOICE_KING_ROLE_COLOR)

        if role is None:
            try:
                role = await guild.create_role(
                    name=config.VOICE_KING_ROLE_NAME,
                    color=role_color,
                    hoist=config.VOICE_KING_ROLE_HOIST,
                    mentionable=False,
                    reason="Роль недельного лидера по времени в голосовых каналах",
                )
                logger.info(f"Создана роль {role.name} ({role.id}) на сервере {guild.name}")
            except discord.Forbidden:
                logger.error(f"Нет прав для создания роли {config.VOICE_KING_ROLE_NAME} на сервере {guild.name}")
                return None
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при создании роли {config.VOICE_KING_ROLE_NAME}: {e}")
                return None

        update_kwargs = {}
        if role.color.value != config.VOICE_KING_ROLE_COLOR:
            update_kwargs["color"] = role_color
        if role.hoist != config.VOICE_KING_ROLE_HOIST:
            update_kwargs["hoist"] = config.VOICE_KING_ROLE_HOIST
        if role.mentionable:
            update_kwargs["mentionable"] = False

        if update_kwargs:
            try:
                await role.edit(**update_kwargs, reason="Синхронизация настроек роли Войс-царя")
            except discord.Forbidden:
                logger.error(f"Нет прав для изменения роли {role.name} ({role.id})")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при изменении роли {role.name}: {e}")

        return role

    def _find_announce_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = config.VOICE_KING_ANNOUNCE_CHANNEL_ID
        if channel_id:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                logger.warning(f"Канал для анонса Войс-царя {channel_id} не найден на сервере {guild.name}")
                return None

            permissions = channel.permissions_for(guild.me)
            if not permissions.view_channel or not permissions.send_messages:
                logger.warning(f"Нет доступа к каналу для анонса Войс-царя {channel_id}")
                return None

            return channel

        candidates = []
        if guild.system_channel:
            candidates.append(guild.system_channel)
        candidates.extend(guild.text_channels)

        for channel in candidates:
            permissions = channel.permissions_for(guild.me)
            if permissions.view_channel and permissions.send_messages:
                return channel

        return None

    def _build_announcement(
        self,
        new_member: discord.Member,
        old_member: Optional[discord.Member],
        seconds: int,
    ) -> str:
        new_name = self._display_name(new_member)
        old_name = self._display_name(old_member) if old_member else None

        if old_member and config.VOICE_KING_TOXIC_ANNOUNCEMENTS:
            text = random.choice(CAPTURE_TEMPLATES).format(new=new_name, old=old_name)
        elif config.VOICE_KING_ANNOUNCE_FIRST_CORONATION:
            text = random.choice(FIRST_CORONATION_TEMPLATES).format(new=new_name)
        else:
            text = f"🎙 {new_name} стал **Войс-царём недели**."

        return f"{text}\n`Недельное время в войсе: {format_time_seconds(seconds)}`"

    async def _announce_new_king(
        self,
        guild: discord.Guild,
        new_member: discord.Member,
        old_member: Optional[discord.Member],
        seconds: int,
    ) -> None:
        channel = self._find_announce_channel(guild)
        if not channel:
            logger.warning(f"Канал для анонса Войс-царя не найден на сервере {guild.name}")
            return

        try:
            await channel.send(
                self._build_announcement(new_member, old_member, seconds),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.Forbidden:
            logger.error(f"Нет прав отправлять анонс Войс-царя в канал {channel.id}")
        except discord.HTTPException as e:
            logger.error(f"Ошибка Discord API при отправке анонса Войс-царя: {e}")

    async def _clear_voice_king_role(self, role: discord.Role, reason: str) -> int:
        """Снять роль Войс-царя со всех текущих держателей."""
        removed = 0
        for holder in self._get_current_role_holders(role.guild, role):
            try:
                await holder.remove_roles(role, reason=reason)
                removed += 1
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.error(f"Не удалось снять роль Войс-царя у {holder.id}: {e}")

        await self._sync_role_name(role, None)
        return removed

    async def sync_guild_voice_king(self, guild: discord.Guild) -> tuple[int, int, int]:
        """Синхронизировать роль Войс-царя на сервере."""
        role = await self.ensure_voice_king_role(guild)
        if role is None:
            return 0, 0, 1

        if not guild.chunked:
            await guild.chunk()

        now = datetime.now()
        live_top = []

        for member in self._iter_live_voice_members(guild):
            seconds = await self._get_live_weekly_seconds(member, now)
            live_top.append((member, seconds))

        live_top.sort(key=lambda item: (-item[1], item[0].display_name.casefold(), item[0].id))

        leader_source = "voice"
        leader_candidates = live_top
        if not leader_candidates or leader_candidates[0][1] < config.VOICE_KING_MIN_SECONDS:
            leader_source = "online"
            leader_candidates = await self._get_weekly_top_members(guild, online_only=True)

        if not leader_candidates or leader_candidates[0][1] < config.VOICE_KING_MIN_SECONDS:
            leader_source = "weekly"
            leader_candidates = await self._get_weekly_top_members(guild)

        if not leader_candidates or leader_candidates[0][1] < config.VOICE_KING_MIN_SECONDS:
            removed = await self._clear_voice_king_role(role, "Нет недельного Войс-царя")
            return 0, removed, 0

        leader, leader_seconds = leader_candidates[0]
        has_top_tie = len(leader_candidates) > 1 and leader_candidates[1][1] == leader_seconds

        await self._sync_role_name(role, leader_seconds)
        if leader_source == "online":
            logger.info(
                f"Активных кандидатов в войсе нет; Войс-царём выбран онлайн-лидер недели "
                f"{leader.display_name} ({leader.id})"
            )
        elif leader_source == "weekly":
            logger.info(
                f"Активных и онлайн-кандидатов нет; Войс-царём выбран общий недельный лидер "
                f"{leader.display_name} ({leader.id})"
            )
        if has_top_tie:
            logger.info(
                f"Ничья Войс-царя на {format_time_seconds(leader_seconds)}; "
                f"по алфавиту выбран {leader.display_name} ({leader.id})"
            )

        holders = self._get_current_role_holders(guild, role)
        old_holder = next((member for member in holders if member.id != leader.id), None)
        changed = 0
        errors = 0

        for holder in holders:
            if holder.id == leader.id:
                continue
            try:
                await holder.remove_roles(role, reason="Войс-царь был обогнан")
                changed += 1
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.error(f"Не удалось снять роль Войс-царя у {holder.id}: {e}")
                errors += 1

        had_role = role in leader.roles
        if not had_role:
            try:
                await leader.add_roles(role, reason="Недельный лидер по времени в голосовых каналах")
                changed += 1
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.error(f"Не удалось выдать роль Войс-царя пользователю {leader.id}: {e}")
                errors += 1

        previous_announced_id = self.last_announced_leaders.get(guild.id)
        if previous_announced_id != leader.id and (old_holder or not had_role):
            await self._announce_new_king(guild, leader, old_holder, leader_seconds)
            self.last_announced_leaders[guild.id] = leader.id

        return len(leader_candidates), changed, errors

    @tasks.loop(seconds=config.VOICE_KING_SYNC_INTERVAL_SECONDS)
    async def sync_voice_king_loop(self):
        """Периодическая синхронизация Войс-царя."""
        for guild in self._get_target_guilds():
            try:
                checked, changed, errors = await self.sync_guild_voice_king(guild)
                if changed or errors:
                    logger.info(
                        f"Синхронизация {config.VOICE_KING_ROLE_NAME}: "
                        f"проверено {checked}, изменений {changed}, ошибок {errors}"
                    )
            except Exception as e:
                logger.error(f"Ошибка синхронизации Войс-царя на сервере {guild.name}: {e}", exc_info=True)

    @sync_voice_king_loop.before_loop
    async def before_sync_voice_king_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Периодическая синхронизация Войс-царя готова к запуску")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Быстро пересобрать Войс-царя при входе/выходе недельного лидера в сеть."""
        if after.bot or before.status == after.status:
            return

        if config.GUILD_ID and after.guild.id != config.GUILD_ID:
            return

        try:
            await self.sync_guild_voice_king(after.guild)
        except Exception as e:
            logger.error(f"Ошибка синхронизации Войс-царя при смене онлайн-статуса {after.id}: {e}", exc_info=True)

    @app_commands.command(name="voice-king", description="Показать текущего Войс-царя и недельный топ войса")
    async def voice_king_command(self, interaction: discord.Interaction):
        """Показать текущего Войс-царя и недельный топ."""
        if not interaction.guild:
            await interaction.response.send_message("❌ Команда доступна только на сервере.", ephemeral=True)
            return

        top = await self.db.get_top_weekly_voice(10)
        if not top:
            await interaction.response.send_message("🎙 Пока никто не набрал время в войсе на этой неделе.", ephemeral=True)
            return

        lines = []
        for index, (user_id, seconds) in enumerate(top, 1):
            member = interaction.guild.get_member(user_id)
            name = self._display_name(member) if member else f"ID {user_id}"
            prefix = "👑" if index == 1 else f"{index}."
            lines.append(f"{prefix} {name} — `{format_time_seconds(seconds)}`")

        embed = discord.Embed(
            title="🎙 Войс-царь недели",
            description="\n".join(lines),
            color=discord.Color(config.VOICE_KING_ROLE_COLOR),
        )
        embed.set_footer(text="Трон держится только до тех пор, пока тебя не обогнали.")
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    await bot.add_cog(VoiceKingCog(bot, bot.db))
