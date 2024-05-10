#!/bin/sh

# Function to display help
show_help() {
    echo "Usage: $0 [OPTION]"
    echo "Options:"
    echo "  --build             Build both GPU and CPU images."
    echo "  --build gpu         Build only the GPU image."
    echo "  --build cpu         Build only the CPU image."
    echo "  --help              Display this help and exit."
    echo "If no options are provided, both images are built."
    echo "Example usage:"
    echo "  $0 --build gpu      Builds only the GPU image."
}

# Function to build images
build_images() {
    if [ "$1" = "gpu" ] || [ -z "$1" ]; then
        echo "Building marker-gpu"
        docker build -f gpu.Dockerfile -t marker-gpu .
    fi
    if [ "$1" = "cpu" ] || [ -z "$1" ]; then
        echo "Building marker-cpu"
        docker build -f cpu.Dockerfile -t marker-cpu .
    fi
}

# Main script starts here
case $1 in
    --build)
        case $2 in
            gpu|cpu)
                build_images $2
                ;;
            '')
                build_images
                ;;
            *)
                show_help
                exit 1
                ;;
        esac
        ;;
    --help)
        show_help
        ;;
    '')
        build_images
        echo "Done"
        ;;
    *)
        show_help
        exit 1
        ;;
esac