with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'BotCommand("deladmin"' in line:
        lines.insert(i+1, '        BotCommand("broadcast", "📣 Barchaga xabar yuborish"),\n')
        break
with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
