#!/usr/bin/env bash

set -euo pipefail

NO_CLEANUP=${NO_CLEANUP:-}
BUILD_IMAGE=${BUILD_IMAGE:-}

echo '# Updating environment'
if [ -z "$BUILD_IMAGE" ]; then
    tag='abesto/openzipkin-contrib-apache-release-verification'
    docker pull "$tag"
else
    tag='local-openzipkin-contrib-apache-release-verification'
    docker build . -t "$tag"
fi

echo "# Executing checks"

cidfile="$(mktemp)"
rm "$cidfile"

if docker run -ti --cidfile "$cidfile" "$tag" "$@" && [ -z "$NO_CLEANUP" ]; then
    echo 'Cleaning up container (set env var NO_CLEANUP=1 to disable this)'
    docker rm "$(cat "$cidfile")"
else
    cat <<EOF

Not cleaning up container.
You can inspect it via the below command:

    image="\$(docker commit "$(cat "$cidfile")")"
    echo "\$image"
    docker run --rm -ti --entrypoint bash "\$image"

To then clean up the temporary image created above and the original container:

    docker rmi "\$image"
    docker rm $(cat "$cidfile")

Alternately, if you're not going to inspect the state of the container,
you can clean it up directly like so:

    docker rm $(cat "$cidfile")
EOF
fi
