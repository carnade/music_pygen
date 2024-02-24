docker buildx create --name nas_builder --use
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64 -t music_pygen:latest . --load
