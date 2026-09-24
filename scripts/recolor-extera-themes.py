from pathlib import Path
from zipfile import ZipFile
import re

root = Path('Telegram/Resources')
night = {
    'windowBg':'#171821', 'windowBgOver':'#242634', 'windowBgRipple':'#303044',
    'windowFg':'#f2efff', 'windowBoldFg':'#faf8ff', 'windowSubTextFg':'#aaa5c1',
    'windowBgActive':'#8b5cf6', 'windowActiveTextFg':'#bba5ff',
    'activeButtonBg':'#8152e5', 'activeButtonBgOver':'#9369ee',
    'activeLineFg':'#a78bfa', 'lightButtonFg':'#ba9dff',
    'filterInputInactiveBg':'#252636', 'filterInputActiveBg':'#2d2b42',
    'dialogsBg':'#11131c', 'dialogsBgOver':'#39304f', 'dialogsBgActive':'#6542a7',
    'dialogsTextFg':'#aaa5be', 'dialogsDateFg':'#a6a0bd',
    'topBarBg':'#242232', 'msgInBg':'#292a3a', 'msgOutBg':'#513c78',
    'msgOutBgSelected':'#7955b5', 'historyComposeAreaBg':'#242232',
    'historyLinkInFg':'#beaaff', 'historyLinkOutFg':'#d2bdff',
    'sideBarBg':'#0b0c14', 'sideBarBgActive':'#42315d',
    'sideBarBgRipple':'#322641',
}
day = {
    'windowBg':'#f8f6ff', 'windowBgOver':'#eeebf8',
    'windowFg':'#201b31', 'windowBoldFg':'#211a32',
    'windowSubTextFg':'#706982', 'windowBgActive':'#7045bd',
    'windowActiveTextFg':'#7045bd', 'activeButtonBg':'#7045bd',
    'activeButtonBgOver':'#865bcf', 'activeLineFg':'#865bcf',
    'filterInputInactiveBg':'#eeebf8', 'filterInputActiveBg':'#e6e1f4',
    'dialogsBg':'#f3f0fa', 'dialogsBgOver':'#e3dbee', 'dialogsBgActive':'#7045bd',
    'topBarBg':'#eeebf8', 'msgInBg':'#ffffff', 'msgOutBg':'#e9d9ff',
    'historyComposeAreaBg':'#eeebf8', 'sideBarBg':'#231a37',
}
for name, colors in [('night.tdesktop-theme', night), ('night-custom-base.tdesktop-theme', night), ('day-blue.tdesktop-theme', day), ('day-custom-base.tdesktop-theme', day)]:
    path = root / name
    with ZipFile(path) as archive:
        members = [(info, archive.read(info.filename)) for info in archive.infolist()]
        comment = archive.comment
    changed = 0
    with ZipFile(path, 'w') as archive:
        archive.comment = comment
        for info, data in members:
            if info.filename == 'colors.tdesktop-theme':
                source = data.decode('utf-8')
                for key, value in colors.items():
                    pattern = rf'(?m)^({re.escape(key)}:\s*)([^;\r\n]+)(;)'
                    source, count = re.subn(pattern, lambda m: m.group(1)+value+m.group(3), source, count=1)
                    changed += count
                data = source.encode('utf-8')
            archive.writestr(info, data)
    print(name, changed)
