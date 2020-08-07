# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

add_files = [('README.md', '.'),
             ('MANIFEST.in', '.'),
             ('LICENSE.txt', '.'),
             ('AUTHORS.txt', '.'),
             ('NOTICE.txt', '.'),
             ('./img_src', 'img_src'),
             ('./spyder', 'spyder'),
            ]
hidden_imports = ['pylint', 'pyls', 'spyder_kernels']
excludes = []
a = Analysis(['spyder/app/start.py'],
             pathex=['C:/Users/Daniel/Documents/Spyder/spyder'],
             binaries=[],
             datas=add_files,
             hiddenimports=hidden_imports,
             hookspath=[],
             runtime_hooks=[],
             excludes=excludes,
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='spyder',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='spyder')
