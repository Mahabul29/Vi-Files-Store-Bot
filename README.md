Files Store Bot
Telegram file store bot: stores posts/documents in a DB channel and serves them via special links.
Features: single & batch links · custom auto delete (/autodelete) · up to 4 force-sub channels · clone bots (/clone) · broadcast · protect content · start/force pictures.
Admin commands: /genlink /batch /cancel /autodelete /broadcast /users /stats /clone /clones /delclone
Setup: add the bot as admin to the DB channel (and force-sub channels), set env vars (see app.json), run python3 main.py or deploy with the Dockerfile.
