# Put your Live2D model here

Copy **all** files from your Live2D model package into this folder, including:

- `live2dcubismcore.min.js`  ← required (the Cubism 4 core runtime)
- `<name>.model3.json`       ← the entry file
- `<name>.moc3`
- `<name>.physics3.json`
- the textures folder (e.g. `<name>.8192/`)
- expressions (`*.exp3.json`), etc.

Then set the entry file in `config.yaml`:

```yaml
live2d:
  model: live2d/<name>.model3.json
```

Example for the bundled sample name:

```yaml
live2d:
  model: live2d/八千代輝夜姫.model3.json
```

> These files are your own assets and are git-ignored on purpose
> (see `.gitignore`). They stay only on your machine.
