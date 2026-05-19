#!/usr/bin/env bash
set -Eeuox pipefail

declare -A aliases=(
	[8.1]='8'
	[9.1]='9 latest'
)

self="$(basename "$BASH_SOURCE")"
cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"

if [ "$#" -eq 0 ]; then
	versions="$(jq -r 'keys | map(@sh) | join(" ")' versions.json)"
	eval "set -- $versions"
fi

# sort version numbers with highest first
IFS=$'\n'; set -- $(sort -rV <<<"$*"); unset IFS

# get the most recent commit which modified any of "$@"
fileCommit() {
	git log -1 --format='format:%H' HEAD -- "$@"
}

# get the most recent commit which modified "$1/Dockerfile" or any file COPY'd from "$1/Dockerfile"
dirCommit() {
    local dir="$1"; shift
    (
        cd "$dir"
        fileCommit \
            Dockerfile \
            $(git show HEAD:./Dockerfile | awk '
                toupper($1) == "COPY" {
                    # Skip the COPY keyword
                    for (i = 2; i < NF; i++) {
                        # Skip --from=build and similar flags
                        if ($i !~ /^--from=/) {
                            # If the path doesnt start with /, assume its a local path
                            if ($i !~ /^\//) {
                                print $i
                            }
                        }
                    }
                }
            ')
    )
}

cat <<-EOH
# this file is generated via https://github.com/valkey-io/valkey-bundle/blob/$(fileCommit "$self")/$self

Maintainers: Roshan Khatri <rvkhatri@amazon.com> (@roshkhatri)
GitRepo: https://github.com/valkey-io/valkey-bundle.git
EOH

# prints "$2$1$3$1...$N"
join() {
	local sep="$1"; shift
	local out; printf -v out "${sep//%/%%}%s" "$@"
	echo "${out#$sep}"
}

for version; do
	export version

	fullVersion="$(jq -r '.[env.version].version' versions.json)"

	versionAliases=()

	rcSuffix=""
	baseVersion="$fullVersion"
	if [[ "$fullVersion" =~ -rc[0-9]+$ ]]; then
		rcSuffix="${fullVersion##*-}"
		baseVersion="${fullVersion%-*}"
	fi

	versionAliases+=( "$fullVersion" )

	currentVersion="$baseVersion"
	while [ "$currentVersion" != "$version" ] && [ "${currentVersion%.*}" != "$currentVersion" ]; do
		currentVersion="${currentVersion%.*}"
		if [ -n "$rcSuffix" ]; then
			versionAliases+=( "$currentVersion-$rcSuffix" )
		else
			versionAliases+=( "$currentVersion" )
		fi
	done

	if [ -z "$rcSuffix" ] && [[ ! " ${versionAliases[*]} " =~ " $version " ]]; then
		versionAliases+=( "$version" )
	fi

	if [ -n "${aliases[$version]:-}" ]; then
		for alias in ${aliases[$version]}; do
			if [ -n "$rcSuffix" ]; then
				versionAliases+=( "$alias-$rcSuffix" )
			else
				versionAliases+=( "$alias" )
			fi
		done
	fi

	for variant in debian alpine; do
		export variant
		dir="$version/$variant"

		commit="$(dirCommit "$dir")"

		if [ "$variant" = 'debian' ]; then
			variantAliases=( "${versionAliases[@]}" )
		else
			variantAliases=( "${versionAliases[@]/%/-$variant}" )
			variantAliases=( "${variantAliases[@]//latest-/}" )
		fi

		if [ "$variant" = 'debian' ]; then
			suite="$(jq -r ".[env.version].debian.version" versions.json)"
            suiteAliases=( "${versionAliases[@]/%/-$suite}" )
            suiteAliases=( "${suiteAliases[@]//latest-/}" )
		    variantAliases+=( "${suiteAliases[@]}" )
        fi


		echo
		cat <<-EOE
			Tags: $(join ', ' "${variantAliases[@]}")
			GitCommit: $commit
			Directory: $dir
		EOE
	done
done
