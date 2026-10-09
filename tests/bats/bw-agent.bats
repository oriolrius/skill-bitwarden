#!/usr/bin/env bats
# Tests for skill/bitwarden/scripts/bw-agent against a fake `bw` CLI.
# Compatible with bats-core >= 1.2.

setup() {
    ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
    BW_AGENT="$ROOT/skill/bitwarden/scripts/bw-agent"
    TMP="$(mktemp -d)"
    export HOME="$TMP/home"; mkdir -p "$HOME"
    export XDG_CONFIG_HOME="$TMP/config" XDG_CACHE_HOME="$TMP/cache"
    export FAKE_BW_STATE="$TMP/state"
    export BW_BIN_DIR="$ROOT/tests/fixtures/fake-bw"
    unset BW_SERVER BW_CLIENTID BW_CLIENTSECRET BW_PASSWORD BW_PASSWORD_FILE BW_PASSWORD_COMMAND \
          BW_SESSION BW_AGENT_PROFILE BW_AGENT_CONFIG BW_AGENT_READ_ONLY BW_AGENT_ALLOW_EXPORT \
          BW_AGENT_NO_CACHE BW_AGENT_CACHE_DIR BITWARDENCLI_APPDATA_DIR BW_HARD_RESET
    CONF_DIR="$XDG_CONFIG_HOME/bw-agent"
    mkdir -p "$CONF_DIR"
}

teardown() { rm -rf "$TMP"; }

write_config() { # write_config <content>
    printf '%s\n' "$1" > "$CONF_DIR/default.env"
    chmod 600 "$CONF_DIR/default.env"
}

good_config() {
    write_config "BW_SERVER=https://bw.example.org
BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD=test-master-password"
}

@test "wrapper help and version need no configuration" {
    run "$BW_AGENT" --wrapper-help
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
    run "$BW_AGENT" --wrapper-version
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

@test "full flow: login + unlock + command" {
    good_config
    run "$BW_AGENT" get password "Example Service"
    [ "$status" -eq 0 ]
    [ "$output" = "fixture-password-not-real" ]
    [ "$(cat "$FAKE_BW_STATE/server")" = "https://bw.example.org" ]
}

@test "secrets never appear in any bw argv" {
    good_config
    run "$BW_AGENT" list items --search example
    [ "$status" -eq 0 ]
    ! grep -q "test-master-password" "$FAKE_BW_STATE/argv.log"
    ! grep -q "test-client-secret" "$FAKE_BW_STATE/argv.log"
    grep -q -- "unlock --passwordenv __BW_AGENT_PW --raw" "$FAKE_BW_STATE/argv.log"
}

@test "final command does not inherit the master password or API secret" {
    good_config
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    # env block of the last (sync) invocation
    last="$(awk '/^--- sync$/{buf=""; f=1} f{buf=buf $0 "\n"} END{printf "%s", buf}' "$FAKE_BW_STATE/env.log")"
    [[ "$last" == *"BW_SESSION="* ]]
    [[ "$last" != *"BW_PASSWORD="* ]]
    [[ "$last" != *"BW_CLIENTSECRET="* ]]
    [[ "$last" != *"__BW_AGENT_PW="* ]]
}

@test "session is cached (mode 600) and reused without unlocking again" {
    good_config
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    cache="$XDG_CACHE_HOME/bw-agent/default.session"
    [ -f "$cache" ]
    mode="$(stat -c '%a' "$cache" 2>/dev/null || stat -f '%Lp' "$cache")"
    [ "$mode" = "600" ]
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    [ "$(cat "$FAKE_BW_STATE/unlock_count")" = "1" ]
}

@test "stale cached session triggers a re-unlock" {
    good_config
    run "$BW_AGENT" sync
    printf 'stale' > "$XDG_CACHE_HOME/bw-agent/default.session"
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    [ "$(cat "$FAKE_BW_STATE/unlock_count")" = "2" ]
}

@test "BW_AGENT_NO_CACHE=1 stores nothing on disk" {
    good_config
    BW_AGENT_NO_CACHE=1 run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    [ ! -e "$XDG_CACHE_HOME/bw-agent/default.session" ]
}

@test "config file readable by others is refused" {
    good_config
    chmod 644 "$CONF_DIR/default.env"
    run "$BW_AGENT" sync
    [ "$status" -ne 0 ]
    [[ "$output" == *"chmod 600"* ]]
}

@test "config file is parsed, never executed" {
    marker="$TMP/pwned"
    write_config "BW_SERVER=\$(touch $marker)
BW_CLIENTID=\`touch $marker\`
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD=test-master-password"
    run "$BW_AGENT" doctor
    [ ! -e "$marker" ]
}

@test "unknown keys in the config file are ignored with a warning" {
    write_config "PATH=/nonexistent
LD_PRELOAD=/tmp/evil.so
BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD=test-master-password"
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    [[ "$output" == *"ignoring unknown key 'PATH'"* ]]
    [[ "$output" == *"ignoring unknown key 'LD_PRELOAD'"* ]]
}

@test "quoted values, export prefix and comments are handled" {
    write_config "# comment
export BW_CLIENTID=\"test-client-id\"
  BW_CLIENTSECRET='test-client-secret'
BW_PASSWORD=test-master-password"
    run "$BW_AGENT" get username "Example Service"
    [ "$status" -eq 0 ]
    [ "$output" = "alice@example.com" ]
}

@test "environment overrides the config file" {
    write_config "BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD=wrong-password"
    BW_PASSWORD=test-master-password run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
}

@test "BW_PASSWORD_FILE unlock" {
    printf 'test-master-password\n' > "$TMP/pw"; chmod 600 "$TMP/pw"
    write_config "BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD_FILE=$TMP/pw"
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
}

@test "BW_PASSWORD_COMMAND unlock" {
    write_config "BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD_COMMAND=printf test-master-password"
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    ! grep -q "test-master-password" "$FAKE_BW_STATE/argv.log"
}

@test "profiles select separate config files and caches" {
    printf '%s\n' "BW_CLIENTID=test-client-id" "BW_CLIENTSECRET=test-client-secret" \
        "BW_PASSWORD=test-master-password" > "$CONF_DIR/work.env"
    chmod 600 "$CONF_DIR/work.env"
    BW_AGENT_PROFILE=work run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    [ -f "$XDG_CACHE_HOME/bw-agent/work.session" ]
    BW_AGENT_PROFILE='../evil' run "$BW_AGENT" sync
    [ "$status" -ne 0 ]
}

@test "missing password source fails clearly" {
    write_config "BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret"
    run "$BW_AGENT" sync
    [ "$status" -eq 5 ]
    [[ "$output" == *"no master password source"* ]]
}

@test "wrong master password fails without wiping CLI state" {
    write_config "BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD=nope"
    mkdir -p "$XDG_CONFIG_HOME/Bitwarden CLI"; touch "$XDG_CONFIG_HOME/Bitwarden CLI/data.json"
    run "$BW_AGENT" sync
    [ "$status" -eq 6 ]
    [ -f "$XDG_CONFIG_HOME/Bitwarden CLI/data.json" ]
}

@test "missing bw CLI fails fast with 127" {
    good_config
    BW_BIN_DIR="$TMP/nowhere" run "$BW_AGENT" sync
    [ "$status" -eq 127 ]
}

@test "server mismatch on a shared CLI state is refused" {
    good_config
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    BW_SERVER=https://other.example.net run "$BW_AGENT" sync
    [ "$status" -eq 4 ]
}

@test "lifecycle commands are blocked" {
    good_config
    for c in login logout lock unlock config serve; do
        run "$BW_AGENT" "$c"
        [ "$status" -eq 2 ]
    done
    run "$BW_AGENT" --session abc list items
    [ "$status" -eq 2 ]
}

@test "export is blocked unless explicitly allowed" {
    good_config
    run "$BW_AGENT" export --format json
    [ "$status" -eq 2 ]
    [[ "$output" == *"BW_AGENT_ALLOW_EXPORT"* ]]
}

@test "read-only mode blocks writes but allows reads" {
    good_config
    export BW_AGENT_READ_ONLY=1
    for c in create edit delete restore move import; do
        run "$BW_AGENT" "$c" item x
        [ "$status" -eq 3 ]
    done
    run "$BW_AGENT" send create
    [ "$status" -eq 3 ]
    run "$BW_AGENT" send "some text"
    [ "$status" -eq 3 ]
    run "$BW_AGENT" send list
    [ "$status" -eq 0 ]
    run "$BW_AGENT" get username "Example Service"
    [ "$status" -eq 0 ]
}

@test "generate and encode run without unlocking" {
    run "$BW_AGENT" generate -ulns --length 24
    [ "$status" -eq 0 ]
    [ ! -e "$FAKE_BW_STATE/unlock_count" ]
}

@test "doctor reports state without printing secrets" {
    good_config
    run "$BW_AGENT" doctor
    [ "$status" -eq 0 ]
    [[ "$output" == *"result:       OK"* ]]
    [[ "$output" != *"test-client-secret"* ]]
    [[ "$output" != *"test-master-password"* ]]
    [[ "$output" != *"test-client-id"* ]]
}

@test "doctor reports missing configuration" {
    run "$BW_AGENT" doctor
    [ "$status" -eq 1 ]
    [[ "$output" == *"INCOMPLETE"* ]]
}

@test "config allowlist matches the public schema" {
    command -v jq >/dev/null || skip "jq not installed"
    schema_keys="$(jq -r '.properties | keys[]' "$ROOT/config/schema.json" | sort | tr '\n' ' ')"
    script_keys="$(sed -n '/^readonly ALLOWED_KEYS=/,/"$/p' "$BW_AGENT" | tr -d '\\"' | sed 's/readonly ALLOWED_KEYS=//' | tr ' ' '\n' | grep -v '^$' | sort | tr '\n' ' ')"
    [ "$schema_keys" = "$script_keys" ]
}

@test "doctor flags untouched template placeholders" {
    cp "$ROOT/config/bw-agent.env.example" "$CONF_DIR/default.env"
    chmod 600 "$CONF_DIR/default.env"
    run "$BW_AGENT" doctor
    [ "$status" -eq 1 ]
    [[ "$output" == *"PLACEHOLDER"* ]]
}

# --- regression tests from the security review --------------------------------

@test "read-only: send options cannot smuggle a create past the policy" {
    good_config
    export BW_AGENT_READ_ONLY=1
    run "$BW_AGENT" send -n list "secret text"
    [ "$status" -eq 3 ]
    run "$BW_AGENT" send --name get "secret text"
    [ "$status" -eq 3 ]
    run "$BW_AGENT" device-approval approve-all
    [ "$status" -eq 3 ]
    run "$BW_AGENT" send template send.text
    [ "$status" -eq 0 ]
}

@test "unknown options before the command are rejected" {
    good_config
    run "$BW_AGENT" -n list send
    [ "$status" -eq 2 ]
    run "$BW_AGENT" --pretty get username "Example Service"
    [ "$status" -eq 0 ]
}

@test "inline comments in the config don't disable read-only mode" {
    write_config "BW_CLIENTID=test-client-id
BW_CLIENTSECRET=test-client-secret
BW_PASSWORD=test-master-password
BW_AGENT_READ_ONLY=1   # block all vault writes"
    run "$BW_AGENT" create item e30=
    [ "$status" -eq 3 ]
}

@test "unrecognised flag values fail closed" {
    good_config
    BW_AGENT_READ_ONLY=yesplease run "$BW_AGENT" sync
    [ "$status" -eq 1 ]
    [[ "$output" == *"invalid value"* ]]
}

@test "an inherited BW_SESSION never triggers a logout" {
    good_config
    run "$BW_AGENT" sync
    sess="$(cat "$FAKE_BW_STATE/session")"
    rm -f "$XDG_CACHE_HOME/bw-agent/default.session"
    : > "$FAKE_BW_STATE/argv.log"
    BW_SESSION="$sess" BW_AGENT_NO_CACHE=1 run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    ! grep -q '^logout' "$FAKE_BW_STATE/argv.log"
}

@test "mkdir lock (no flock) is released after the command" {
    good_config
    _BW_AGENT_TEST_NO_FLOCK=1 run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    [ ! -e "$XDG_CACHE_HOME/bw-agent/default.lock.d" ]
}

@test "flock fd is not inherited by the final bw command" {
    [ -d /proc/self/fd ] || skip "needs /proc"
    good_config
    run "$BW_AGENT" sync
    [ "$status" -eq 0 ]
    # auth helpers run while the lock is held; the user's command must not
    ! grep -q "leaked: sync" "$FAKE_BW_STATE/fd.log"
}
