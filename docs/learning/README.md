# Material de aprendizaje de ft_otp

Documentos educativos que explican cómo y por qué funciona el código del proyecto.

- [001 - Estructura del proyecto Python](001-estructura-proyecto-python.md): por qué se pasó de un layout plano al *src layout* y cómo funcionan paquetes, `__init__.py`, `__main__.py`, `sys.path`, `pyproject.toml`, puntos de entrada, códigos de salida, tests y `.gitignore`.
- [002 - Conceptos para rediseñar ft_otp](002-conceptos-criptografia-otp.md): lección de conceptos (sin cambios de código) sobre bytes/hex/base32, HMAC, HOTP y TOTP con los vectores de las RFC, semillas, `otpauth://` y QR, cifrado autenticado (Fernet, AES-GCM), el secreto en `.env` con permisos `0600`, frase de paso frente a KDF, la sal, pruebas contra `oathtool` y un primer contacto con PySide6.
