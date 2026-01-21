import discord
from discord.ext import commands, tasks
import aiohttp
import os
import sys
import tempfile
import json
import atexit
from datetime import datetime

# =======================
# BEÁLLÍTÁSOK
# =======================
TOKEN = os.getenv("TOKEN")
API_URL = "https://mapa.idsjmk.cz/api/vehicles.json"

LOCK_FILE = "/tmp/discord_bot.lock"

if os.path.exists(LOCK_FILE):
    print("A bot már fut, kilépés.")
    sys.exit(0)

# =======================
# SEGÉDFÜGGVÉNYEK
# =======================
def ensure_dirs():
    os.makedirs("logs", exist_ok=True)
    os.makedirs("logs/veh", exist_ok=True)

def is_t6(reg):
    """1200-1299 T6 villamosok"""
    try:
        n = int(reg)
        return 1200 <= n <= 1299
    except:
        return False

def is_t2(reg):
    """1200-1299 T6 villamosok"""
    try:
        n = int(reg)
        return 1425 <= n <= 1426
    except:
        return False

def is_k2(reg):
    """1200-1299 T6 villamosok"""
    try:
        n = int(reg)
        return 1080 or 1123 or 1018
    except:
        return False

def is_k3(reg):
    """1200-1299 T6 villamosok"""
    try:
        n = int(reg)
        return 1750 <= n <= 1753
    except:
        return False

def is_t3(reg):
    """1500–1699 T3 villamosok"""
    try:
        n = int(reg)
        return 1500 <= n <= 1699
    except:
        return False

def is_kt8(reg):
    """1700-1749 KT8 villamosok"""
    try:
        n = int(reg)
        return 1700 <= n <= 1749
    except:
        return False

def save_trip(trip_id, line, vehicle, dest):
    ensure_dirs()
    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    trip_dir = f"logs/{today}"
    os.makedirs(trip_dir, exist_ok=True)

    # Mentés járatonként
    trip_file = f"{trip_dir}/{trip_id}.txt"
    if not os.path.exists(trip_file):
        with open(trip_file, "w", encoding="utf-8") as f:
            f.write(
                f"Dátum: {today}\n"
                f"ID: {trip_id}\n"
                f"Vonal: {line}\n"
                f"Cél: {dest}\n"
                f"Jármű: {vehicle}\n"
                f"Első észlelés: {ts}\n"
            )

    # Mentés jármű szerint
    veh_file = f"logs/veh/{vehicle}.txt"
    last_id = None
    if os.path.exists(veh_file):
        with open(veh_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            if lines and "ID " in lines[-1]:
                last_id = lines[-1].split("ID ")[1].split(" ")[0]

    if last_id != trip_id:
        with open(veh_file, "a", encoding="utf-8") as f:
            f.write(f"{ts} - ID {trip_id} - Vonal {line} - {dest}\n")

# =======================
# DISCORD INIT
# =======================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

# =======================
# LOGGER LOOP
# =======================
@tasks.loop(seconds=30)
async def logger_loop():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as r:
                if r.status != 200:
                    print("Hiba a JSON lekéréskor:", r.status)
                    return
                text = await r.text(encoding="utf-8-sig")  # BOM kezelése
                data = json.loads(text)
        except Exception as e:
            print("Hiba a JSON lekéréskor:", e)
            return

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", "Unknown"))          # Pályaszám/ID
            trip_id = str(v.get("Course", "Unknown"))           # Forgalmi
            line = v.get("LineName", "Ismeretlen")             # Vonal
            dest = v.get("FinalStopName", "Ismeretlen")        # Célállomás
            lat = v.get("Lat")
            lon = v.get("Lng")

            if lat is None or lon is None:
                continue  # Ha nincs pozíció, nem mentjük

            # Mentés a naplóba
            save_trip(trip_id, line, vehicle_label, dest)

# =======================
# PARANCSOK
# =======================
                
# @bot.command()
# async def dpmbtatra(ctx, date: str = None):
#     day = date or datetime.now().strftime("%Y-%m-%d")
#     veh_dir = "logs/veh"
#     tatras = {}

#     for fname in os.listdir(veh_dir):
#         if not fname.endswith(".txt"):
#             continue

#         reg = fname.replace(".txt", "")

#         # Pályaszám kötelező
#         if not reg.isdigit():
#             continue

#         # 🔒 KÖZPONTI SZŰRŐ – CSAK EZEK JÖHETNEK ÁT
#         is_tatra = (
#             is_t2(reg)
#             or is_t3(reg)
#             or is_t6(reg)
#             or is_k2(reg)
#             or is_k3(reg)
#             or is_kt8(reg)
#         )

#         if not is_tatra:
#             continue  # ⛔ minden más kuka

#         num = int(reg)

#         # Altípus
#         subtype = "Tatra (ismeretlen)"

#         if is_t3(reg):
#             if num in [1604, 1606, 1607, 1608, 1611, 1613, 1614, 1619, 1631, 1634, 1639, 1640, 1651, 1652]:
#                 subtype = "Tatra T3G"
#             elif num in [1517, 1558, 1561, 1603] or 1653 <= num <= 1658:
#                 subtype = "Tatra T3R.PV"
#             elif num in [1564, 1576, 1583, 1587, 1589, 1620, 1628, 1629]:
#                 subtype = "Tatra T3P"
#             elif 1661 <= num <= 1666:
#                 subtype = "Tatra T3R"
#             elif num == 1615:
#                 subtype = "Tatra T3R *nosztalgia*"
#             elif num == 1525:
#                 subtype = "Tatra T3 *nosztalgia*"
#             elif num in [1531, 1560, 1562, 1569]:
#                 subtype = "Tatra T3R.EV"

#         elif is_t6(reg):
#             subtype = "Tatra T6A5"

#         elif is_k3(reg):
#             subtype = "Tatra K3R-N"

#         elif is_kt8(reg):
#             if 1729 <= num <= 1735:
#                 subtype = "Tatra KT8D5N"
#             else:
#                 subtype = "Tatra KT8D5R.N2"

#         elif is_t2(reg):
#             subtype = "Tatra T2 *nosztalgia*"

#         elif is_k2(reg):
#             if num == 1018:
#                 subtype = "Tatra K2R-RT"
#             elif num == 1080:
#                 subtype = "Tatra K2P"
#             elif num == 1123:
#                 subtype = "Tatra K2YU *nosztalgia*"

#         # 📖 LOG OLVASÁS – CSAK A MEGFELELŐ JÁRMŰVEKHEZ
#         with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
#             for line in f:
#                 if not line.startswith(day):
#                     continue

#                 trip_id = line.split("ID ")[1].split(" ")[0]
#                 line_no = line.split("Vonal ")[1].split(" ")[0]
#                 dest = line.split(" - ")[-1].strip()

#                 tatras.setdefault(reg, []).append(
#                     (subtype, line_no, trip_id, dest)
#                 )

#     if not tatras:
#         return await ctx.send(f"🚫 {day} napon nem volt forgalomban Tatra villamos.")

#     # EMBED
#     MAX_FIELDS = 20
#     embeds = []

#     embed = discord.Embed(
#         title=f"🚋 Tatra villamosok ({day})",
#         color=0xff0000
#     )
#     field_count = 0

#     for reg, records in sorted(tatras.items(), key=lambda x: int(x[0])):
#         if field_count >= MAX_FIELDS:
#             embeds.append(embed)
#             embed = discord.Embed(
#                 title=f"🚋 Tatra villamosok ({day}) – folytatás",
#                 color=0xff0000
#             )
#             field_count = 0

#         subtype, line_no, trip_id, dest = records[0]

#         embed.add_field(
#             name=reg,
#             value=(
#                 f"Altípus: {subtype}\n"
#                 f"Vonal: {line_no}\n"
#                 f"Forgalmi: {trip_id}\n"
#                 f"Cél: {dest}"
#             ),
#             inline=False
#         )

#         field_count += 1

#     embeds.append(embed)

#     for e in embeds:
#         await ctx.send(embed=e)
                
@bot.command()
async def dpmbt3today(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_t3(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett T3-as villamos.")

    out = [f"🚋 T3 – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmbt3(ctx):
    active = {}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as r:
                if r.status != 200:
                    return await ctx.send(f"❌ Hiba az API lekéréskor: {r.status}")
                text = await r.text(encoding="utf-8-sig")
                data = json.loads(text)
        except Exception as e:
            return await ctx.send(f"❌ Hiba az API lekéréskor: {e}")

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", ""))
            trip_id = str(v.get("Course", "Unknown"))  # Forgalmi
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_t3(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            # Altípus meghatározása
            num = int(vehicle_label) if vehicle_label.isdigit() else 0
            if num in [1604, 1606, 1607, 1608, 1611, 1613, 1614, 1619, 1631, 1634, 1639, 1640, 1651, 1652]:
                subtype = "Tatra T3G"
            elif num in [1517, 1558, 1561, 1603] or 1653 <= num <= 1658:
                subtype = "Tatra T3R.PV"
            elif num in [1564, 1576, 1583, 1587, 1589, 1620, 1628, 1629]:
                subtype = "Tatra T3P"
            elif num == 1661 <= num <= 1666:
                subtype = "Tatra T3R"
            elif num == 1615:
                subtype = "Tatra T3R *nosztalgia*"
            elif num in [1531, 1560, 1562, 1569]:
                subtype = "Tatra T3R.EV"
            elif num == 1525:
                subtype = "Tatra T3 *nosztalgia*"
            else:
                subtype = "T3 (ismeretlen)"

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon,
                "subtype": subtype
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív T3-as villamos.")

    # EMBED DARABOLÁS
    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív T3 villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(title="🚋 Aktív T3 villamosok (folytatás)", color=0xff0000)
            field_count = 0

        embed.add_field(
            name=f"{reg}",
            value=f"Altípus: {i['subtype']}\nVonal: {i['line']}\nForgalmi: {i['trip']}\nCél: {i['dest']}",
            inline=False
        )
        field_count += 1

    embeds.append(embed)
    for e in embeds:
        await ctx.send(embed=e)


@bot.command()
async def dpmbt6today(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_t6(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett T6A5 villamos.")

    out = [f"🚋 T6A5 – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmbt6(ctx):
    active = {}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as r:
                if r.status != 200:
                    return await ctx.send(f"❌ Hiba az API lekéréskor: {r.status}")
                text = await r.text(encoding="utf-8-sig")  # BOM kezelése
                data = json.loads(text)
        except Exception as e:
            return await ctx.send(f"❌ Hiba az API lekéréskor: {e}")

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", ""))
            trip_id = str(v.get("Course", "Unknown"))     # Forgalmi
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            # Csak T3-asok
            if not is_t6(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,    # hozzáadva a forgalmi
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív T6A5 villamos.")

    # EMBED DARABOLÁS
    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív T6A5 villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(title="🚋 Aktív T6A5 villamosok (folytatás)", color=0xff0000)
            field_count = 0

        embed.add_field(
            name=f"{reg}",
            value=f"Vonal: {i['line']}\nForgalmi: {i['trip']}\nCél: {i['dest']}",
            inline=False
        )
        field_count += 1

    embeds.append(embed)
    for e in embeds:
        await ctx.send(embed=e)

@bot.command()
async def dpmbk3today(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_k3(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett K3R-N villamos.")

    out = [f"🚋 K3R-N – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmbk3(ctx):
    active = {}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as r:
                if r.status != 200:
                    return await ctx.send(f"❌ Hiba az API lekéréskor: {r.status}")
                text = await r.text(encoding="utf-8-sig")  # BOM kezelése
                data = json.loads(text)
        except Exception as e:
            return await ctx.send(f"❌ Hiba az API lekéréskor: {e}")

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", ""))
            trip_id = str(v.get("Course", "Unknown"))     # Forgalmi
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            # Csak T3-asok
            if not is_k3(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,    # hozzáadva a forgalmi
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív K3R-N villamos.")

    # EMBED DARABOLÁS
    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív K3R-N villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(title="🚋 Aktív K3R-N villamosok (folytatás)", color=0xff0000)
            field_count = 0

        embed.add_field(
            name=f"{reg}",
            value=f"Vonal: {i['line']}\nForgalmi: {i['trip']}\nCél: {i['dest']}",
            inline=False
        )
        field_count += 1

    embeds.append(embed)
    for e in embeds:
        await ctx.send(embed=e)


@bot.command()
async def dpmbk2today(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_k2(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett K2 villamos.")

    out = [f"🚋 K2 – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmbk2(ctx):
    active = {}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as r:
                if r.status != 200:
                    return await ctx.send(f"❌ Hiba az API lekéréskor: {r.status}")
                text = await r.text(encoding="utf-8-sig")  # BOM kezelése
                data = json.loads(text)
        except Exception as e:
            return await ctx.send(f"❌ Hiba az API lekéréskor: {e}")

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", ""))
            trip_id = str(v.get("Course", "Unknown"))     # Forgalmi
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            # Csak T3-asok
            if not is_k2(vehicle_label):
                continue
            if lat is None or lon is None:
                continue 
            #Altípus meghatározása
            num = int(vehicle_label) if vehicle_label.isdigit() else 0
            if num == 1018:
                subtype = "Tatra K2R-RT"
            elif num == 1080:
                subtype = "Tatra K2P"
            else:
                subtype = "Tatra K2YU *nosztalgia*"

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,    # hozzáadva a forgalmi
                "lat": lat,
                "lon": lon,
                "subtype": subtype
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív K2 villamos.")

    # EMBED DARABOLÁS
    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív K2 villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(title="🚋 Aktív K2 villamosok (folytatás)", color=0xff0000)
            field_count = 0

        embed.add_field(
            name=f"{reg}",
            value=f"Altípus: {i['subtype']}\nVonal: {i['line']}\nForgalmi: {i['trip']}\nCél: {i['dest']}",
            inline=False
        )
        field_count += 1

    embeds.append(embed)
    for e in embeds:
        await ctx.send(embed=e)


@bot.command()
async def dpmbt2today(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_t2(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett T2 villamos.")

    out = [f"🚋 T2 – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmbt2(ctx):
    active = {}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as r:
                if r.status != 200:
                    return await ctx.send(f"❌ Hiba az API lekéréskor: {r.status}")
                text = await r.text(encoding="utf-8-sig")  # BOM kezelése
                data = json.loads(text)
        except Exception as e:
            return await ctx.send(f"❌ Hiba az API lekéréskor: {e}")

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", ""))
            trip_id = str(v.get("Course", "Unknown"))     # Forgalmi
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            # Csak T3-asok
            if not is_t2(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,    # hozzáadva a forgalmi
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív T2 villamos.")

    # EMBED DARABOLÁS
    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív T2 villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(title="🚋 Aktív T2 villamosok (folytatás)", color=0xff0000)
            field_count = 0

        embed.add_field(
            name=f"{reg}",
            value=f"Vonal: {i['line']}\nForgalmi: {i['trip']}\nCél: {i['dest']}",
            inline=False
        )
        field_count += 1

    embeds.append(embed)
    for e in embeds:
        await ctx.send(embed=e)



@bot.command()
async def dpmbkt8today(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_kt8(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett KT8D villamos.")

    out = [f"🚋 KT8D – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmbkt8(ctx):
    active = {}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as r:
                if r.status != 200:
                    return await ctx.send(f"❌ Hiba az API lekéréskor: {r.status}")
                text = await r.text(encoding="utf-8-sig")  # BOM kezelése
                data = json.loads(text)
        except Exception as e:
            return await ctx.send(f"❌ Hiba az API lekéréskor: {e}")

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", ""))
            trip_id = str(v.get("Course", "Unknown"))     # Forgalmi
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            # Csak KT8D villamosok
            if not is_kt8(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            # Altípus meghatározása
            num = int(vehicle_label) if vehicle_label.isdigit() else 0
            if 1729 <= num <= 1735:
                subtype = "Tatra KT8D5N"
            else:
                subtype = "Tatra KT8D5R.N2"

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon,
                "subtype": subtype
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív KT8D villamos.")

    # EMBED DARABOLÁS
    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív KT8D villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(title="🚋 Aktív KT8D villamosok (folytatás)", color=0xff0000)
            field_count = 0

        embed.add_field(
            name=f"{reg}",
            value=f"Altípus: {i['subtype']}\nVonal: {i['line']}\nForgalmi: {i['trip']}\nCél: {i['dest']}",
            inline=False
        )
        field_count += 1

    embeds.append(embed)
    for e in embeds:
        await ctx.send(embed=e)



# =======================
# START
# =======================
@bot.event
async def on_ready():
    if getattr(bot, "ready_done", False):
        return
    bot.ready_done = True
    ensure_dirs()
    print(f"Bejelentkezve mint {bot.user}")
    logger_loop.start()

bot.run(TOKEN)

