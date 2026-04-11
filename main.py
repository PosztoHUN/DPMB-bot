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

# jármű+forgalmi → utolsó log idő
last_seen = {}
LOG_INTERVAL = 300  # másodperc (5 perc)

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
        return 1435 <= n <= 1436
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
        return 1751 <= n <= 1754
    except:
        return False

def is_t3(reg):
    """1500–1699 T3 villamosok"""
    try:
        n = int(reg)
        return n in {
            1604, 1606, 1607, 1608, 1611, 1613, 1614, 1619,
            1631, 1634, 1639, 1640, 1651, 1652,
            1517, 1558, 1561, 1603,
            1653, 1654, 1655, 1656, 1657, 1658,
            1564, 1576, 1583, 1587, 1589, 1620, 1628, 1629,
            1661, 1662, 1663, 1664, 1665, 1666,
            1615,
            1531, 1560, 1562, 1569,
            1525
        }
    except ValueError:
        return False

def is_kt8(reg):
    """1700-1749 KT8 villamosok"""
    try:
        n = int(reg)
        return 1700 <= n <= 1749
    except:
        return False
    
def is_9tr(reg):    
    try:
        n = int(reg)
        return n in{3076, 3136}
    except:
        return False
    
def is_14tr(reg):   
    try:
        n = int(reg)
        return n in{3173, 3283}
    except:
        return False
    
def is_15tr(reg):   
    try:
        n = int(reg)
        return n in{3501, 3502}
    except:
        return False
    
def is_21tr(reg):   
    try:
        n = int(reg)
        return n in{3030, 3063}
    except:
        return False
    
def is_22tr(reg):   
    try:
        n = int(reg)
        return n in{3601}
    except:
        return False
    
def is_26tr(reg):   
    try:
        n = int(reg)
        return 3301 <= n <= 3310
    except:
        return False
    
def is_27tr(reg):   
    try:
        n = int(reg)
        return 3648 <= n <= 3687
    except:
        return False
    
def is_31tr(reg):   
    try:
        n = int(reg)
        return 3618 <= n <= 3647
    except:
        return False
    
def is_32tr(reg):   
    try:
        n = int(reg)
        return 3311 <= n <= 3345
    except:
        return False
    
def is_evo(reg):   
    try:
        n = int(reg)
        return 1822 <= n <= 1862
    except:
        return False
    
def is_antira(reg):
    try:
        n = int(reg)
        return 1806 <= n <= 1819
    except:
        return False
    
def is_13t(reg):
    try:
        n = int(reg)
        return 1901 <= n <= 1949
    except:
        return False
    
def is_45t(reg):
    try:
        n = int(reg)
        return 1760 <= n <= 1789
    except:
        return False
    
def is_lf2(reg):
    try:
        n = int(reg)
        return n in {1069, 1072, 1078, 1082, 1083, 1084, 1088, 1090, 1092, 1093, 1094, 1096, 1098, 1099, 1100, 1101, 1102, 1103, 1106, 1108, 1109, 1110, 1112, 1114, 1117, 1120, 1126, 1127, 1128, 1130, 1131, 1132}
    except:
        return False

def is_lfr(reg):
    try:
        n = int(reg)
        return n in {1497, 1523, 1530, 1539, 1541, 1551, 1553, 1554, 1555, 1556, 1557, 1567, 1573, 1574, 1575, 1580, 1582, 1584, 1586, 1590, 1592, 1596, 1597, 1598, 1599, 1601, 1605, 1616, 1617, 1626, 1627, 1630}
    except:
        return False

def save_trip(trip_id, line, vehicle, dest):
    ensure_dirs()

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    ts = now.strftime("%Y-%m-%d %H:%M:%S")

    trip_dir = f"logs/{today}"
    os.makedirs(trip_dir, exist_ok=True)

    # =========================
    # JÁRAT NAPLÓ (ELSŐ ÉSZLELÉS)
    # =========================
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

    # =========================
    # JÁRMŰ NAPLÓ (FRISSÍTÉS)
    # =========================
    veh_file = f"logs/veh/{vehicle}.txt"
    os.makedirs("logs/veh", exist_ok=True)

    key = f"{vehicle}_{trip_id}"

    write_log = False

    # ha még sosem láttuk → írunk
    if key not in last_seen:
        write_log = True

    # ha már láttuk, de eltelt 5 perc → írunk
    else:
        delta = (now - last_seen[key]).total_seconds()
        if delta >= LOG_INTERVAL:
            write_log = True

    # ha forgalmi váltás volt → azonnal írunk
    if os.path.exists(veh_file):
        with open(veh_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            if lines and "ID " in lines[-1]:
                last_trip = lines[-1].split("ID ")[1].split(" ")[0]
                if last_trip != trip_id:
                    write_log = True

    if write_log:
        with open(veh_file, "a", encoding="utf-8") as f:
            f.write(f"{ts} - ID {trip_id} - Vonal {line} - {dest}\n")
        last_seen[key] = now


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
                
@bot.command()
async def dpmbtatra(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    tatras = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue

        reg = fname.replace(".txt", "")
        if not reg.isdigit():
            continue

        num = int(reg)

        # 🔒 CSAK TATRA
        subtype = None
        if is_t2(reg):
            subtype = "Tatra T2 *nosztalgia*"
        elif is_t3(reg):
            if num in [1604, 1606, 1607, 1608, 1611, 1613, 1614, 1619, 1631, 1634, 1639, 1640, 1651, 1652]:
                subtype = "Tatra T3G"
            elif num in [1517, 1558, 1561, 1603] or 1653 <= num <= 1658:
                subtype = "Tatra T3R.PV"
            elif num in [1564, 1576, 1583, 1587, 1589, 1620, 1628, 1629]:
                subtype = "Tatra T3P"
            elif 1661 <= num <= 1666:
                subtype = "Tatra T3R"
            elif num == 1615:
                subtype = "Tatra T3R *nosztalgia*"
            elif num == 1525:
                subtype = "Tatra T3 *nosztalgia*"
            elif num in [1531, 1560, 1562, 1569]:
                subtype = "Tatra T3R.EV"
            else:
                subtype = "Tatra T3 (ismeretlen)"
        elif is_t6(reg):
            subtype = "Tatra T6A5"
        elif is_k2(reg):
            if num == 1018:
                subtype = "Tatra K2R-RT"
            elif num == 1080:
                subtype = "Tatra K2P"
            elif num == 1123:
                subtype = "Tatra K2YU *nosztalgia*"
            else:
                subtype = None  # nem Tatra
        elif is_k3(reg):
            subtype = "Tatra K3R-N"
        elif is_kt8(reg):
            if 1729 <= num <= 1735:
                subtype = "Tatra KT8D5N"
            else:
                subtype = "Tatra KT8D5R.N2"

        # Ha nem Tatra, ugorjuk át
        if subtype is None:
            continue

        # 📖 LOG OLVASÁS
        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith(day):
                    continue

                trip_id = line.split("ID ")[1].split(" ")[0]
                line_no = line.split("Vonal ")[1].split(" ")[0]
                dest = line.split(" - ")[-1].strip()

                tatras.setdefault(reg, []).append(
                    (subtype, line_no, trip_id, dest)
                )

    if not tatras:
        return await ctx.send(f"🚫 {day} napon nem volt forgalomban Tatra villamos.")

    # EMBED KÜLDÉS
    MAX_FIELDS = 20
    embeds = []

    embed = discord.Embed(
        title=f"🚋 Tatra villamosok ({day})",
        color=0xff0000
    )
    field_count = 0

    for reg, records in sorted(tatras.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title=f"🚋 Tatra villamosok ({day}) – folytatás",
                color=0xff0000
            )
            field_count = 0

        subtype, line_no, trip_id, dest = records[0]

        embed.add_field(
            name=reg,
            value=(
                f"Altípus: {subtype}\n"
                f"Vonal: {line_no}\n"
                f"Forgalmi: {trip_id}\n"
                f"Cél: {dest}"
            ),
            inline=False
        )

        field_count += 1

    embeds.append(embed)

    for e in embeds:
        await ctx.send(embed=e)
                
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
            elif num in [1661, 1662, 1663, 1664, 1665, 1666]:
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
                text = await r.text(encoding="utf-8-sig")
                data = json.loads(text)
        except Exception as e:
            return await ctx.send(f"❌ Hiba az API lekéréskor: {e}")

        vehicles = data.get("Vehicles", [])
        for v in vehicles:
            vehicle_label = str(v.get("ID", ""))
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_t6(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív T6A5 villamos.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív T6A5 villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív T6A5 villamosok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        try:
            reg_num = int(reg)
            if 1221 <= reg_num <= 1248:
                value_text += "\n*🛠️ Tervezett kivonás: 2026. tavasz*"
        except ValueError:
            pass

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
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
                    return await ctx.send(f"❌ API hiba: {r.status}")

                text = await r.text(encoding="utf-8-sig")
                data = json.loads(text)

        except Exception as e:
            return await ctx.send(f"❌ API hiba: {e}")

    vehicles = data.get("Vehicles", [])

    for v in vehicles:
        line = v.get("LineName")
        if line != "K2":
            continue   # 🔴 EZ HIÁNYZOTT

        vehicle_label = str(v.get("ID", ""))
        lat = v.get("Lat")
        lon = v.get("Lng")

        if lat is None or lon is None:
            continue

        trip_id = str(v.get("Course", "Ismeretlen"))
        dest = v.get("FinalStopName", "Ismeretlen")

        active[vehicle_label] = {
            "line": line,
            "dest": dest,
            "trip": trip_id,
            "lat": lat,
            "lon": lon
        }

    if not active:
        return await ctx.send("🚫 Nincs aktív K2 villamos.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív K2 villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív K2 villamosok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        embed.add_field(
            name=reg,
            value=(
                f"Vonal: {i['line']}\n"
                f"Forgalmi: {i['trip']}\n"
                f"Cél: {i['dest']}"
            ),
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
        
@bot.command()
async def dpmbvario(ctx):
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

            if not is_lf2(vehicle_label) or not is_lfr(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            # Altípus meghatározása
            num = int(vehicle_label) if vehicle_label.isdigit() else 0
            if is_lf2(vehicle_label):
                subtype = "Vario LF2R.E"
            elif is_lfr(vehicle_label):
                subtype = "Vario LFR.E"
            else:
                subtype = "Ismeretlen"

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon,
                "subtype": subtype
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Vario villamos.")

    # EMBED DARABOLÁS
    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Vario villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(title="🚋 Aktív Vario villamosok (folytatás)", color=0xff0000)
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
async def dpmbanitra(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_antira(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Anitra villamos.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Anitra villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív Anitra villamosok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
    for e in embeds:
        await ctx.send(embed=e)
        
@bot.command()
async def dpmbevo(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_evo(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív EVO 2 villamos.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív EVO 2 villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív EVO 2 villamosok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
    for e in embeds:
        await ctx.send(embed=e)
        
@bot.command()
async def dpmb13t(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_13t(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Skoda 13T villamos.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Skoda 13T villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív Skoda 13T villamosok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
    for e in embeds:
        await ctx.send(embed=e)
        
@bot.command()
async def dpmbanitra(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_45t(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Anitra villamos.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Anitra villamosok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív Anitra villamosok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
    for e in embeds:
        await ctx.send(embed=e)
        
#=======================
# SKODA Trolik
#=======================

@bot.command()
async def dpmb26trtoday(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_26tr(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett Skoda 26Tr trolibusz.")

    out = [f"🚋 Skoda 26Tr – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmb26tr(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_26tr(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Skoda 26Tr trolibusz.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Skoda 26Tr trolibuszok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív Skoda 26Tr trolibuszok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
    for e in embeds:
        await ctx.send(embed=e)
        
@bot.command()
async def dpmb27trtoday(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_27tr(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett Skoda 27Tr trolibusz.")

    out = [f"🚋 Skoda 27Tr – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmb27tr(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_27tr(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Skoda 27Tr trolibusz.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Skoda 27Tr trolibuszok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív Skoda 27Tr trolibuszok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
    for e in embeds:
        await ctx.send(embed=e)
        
@bot.command()
async def dpmb31trtoday(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_31tr(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett Skoda 31Tr trolibusz.")

    out = [f"🚋 Skoda 31Tr – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmb31tr(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_31tr(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Skoda 31Tr trolibusz.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Skoda 31Tr trolibuszok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív Skoda 31Tr trolibuszok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
    for e in embeds:
        await ctx.send(embed=e)

@bot.command()
async def dpmb32trtoday(ctx, date: str = None):
    day = date or datetime.now().strftime("%Y-%m-%d")
    veh_dir = "logs/veh"
    t3s = {}

    for fname in os.listdir(veh_dir):
        if not fname.endswith(".txt"):
            continue
        reg = fname.replace(".txt","")
        if not is_32tr(reg):
            continue

        with open(os.path.join(veh_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(day):
                    ts = line.split(" - ")[0]
                    trip_id = line.split("ID ")[1].split(" ")[0]
                    line_no = line.split("Vonal ")[1].split(" ")[0]
                    t3s.setdefault(reg, []).append((ts, line_no, trip_id))

    if not t3s:
        return await ctx.send(f"🚫 {day} napon nem közlekedett Skoda 32Tr trolibusz.")

    out = [f"🚋 Skoda 32Tr – forgalomban ({day})"]
    for reg in sorted(t3s):
        first = min(t3s[reg], key=lambda x: x[0])
        last = max(t3s[reg], key=lambda x: x[0])
        out.append(f"{reg} — {first[0][11:16]} → {last[0][11:16]} (vonal {first[1]})")

    msg = "\n".join(out)
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

@bot.command()
async def dpmb32tr(ctx):
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
            trip_id = str(v.get("Course", "Unknown"))
            line = v.get("LineName", "Ismeretlen")
            dest = v.get("FinalStopName", "Ismeretlen")
            lat = v.get("Lat")
            lon = v.get("Lng")

            if not is_32tr(vehicle_label):
                continue
            if lat is None or lon is None:
                continue

            active[vehicle_label] = {
                "line": line,
                "dest": dest,
                "trip": trip_id,
                "lat": lat,
                "lon": lon
            }

    if not active:
        return await ctx.send("🚫 Nincs aktív Skoda 32Tr trolibusz.")

    MAX_FIELDS = 20
    embeds = []
    embed = discord.Embed(title="🚋 Aktív Skoda 32Tr trolibuszok", color=0xff0000)
    field_count = 0

    for reg, i in sorted(active.items(), key=lambda x: int(x[0])):
        if field_count >= MAX_FIELDS:
            embeds.append(embed)
            embed = discord.Embed(
                title="🚋 Aktív Skoda 32Tr trolibuszok (folytatás)",
                color=0xff0000
            )
            field_count = 0

        value_text = (
            f"Vonal: {i['line']}\n"
            f"Forgalmi: {i['trip']}\n"
            f"Cél: {i['dest']}"
        )

        embed.add_field(
            name=f"{reg}",
            value=value_text,
            inline=False
        )
        field_count += 1

    # Csak akkor adjuk hozzá az utolsó embedet, ha nem üres
    if embed.fields:
        embeds.append(embed)

    # KÜLDÉS ASZINKRON FÜGGVÉNYEN BELÜL
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

