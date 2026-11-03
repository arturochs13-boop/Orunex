/**
 * @file bmd_main.c
 * @brief Command Line Interface & Management Utility for Blockchain Markdown (.bmd)
 */

#include "bmd_engine.h"
#include "bmd_crypto.h"
#include "bmd_ledger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

char* getenv(const char* name);
#ifdef _WIN32
char* _fullpath(char* absPath, const char* relPath, size_t maxLength);
#endif

#ifdef _WIN32
typedef void* HANDLE;
typedef unsigned long DWORD;
typedef int BOOL;
#define STD_OUTPUT_HANDLE ((DWORD)-11)
#define ENABLE_VIRTUAL_TERMINAL_PROCESSING 0x0004
__declspec(dllimport) HANDLE __stdcall GetStdHandle(DWORD nStdHandle);
__declspec(dllimport) BOOL __stdcall GetConsoleMode(HANDLE hConsoleHandle, DWORD* lpMode);
__declspec(dllimport) BOOL __stdcall SetConsoleMode(HANDLE hConsoleHandle, DWORD dwMode);
__declspec(dllimport) BOOL __stdcall SetConsoleOutputCP(unsigned int wCodePageID);
__declspec(dllimport) void __stdcall Sleep(unsigned long dwMilliseconds);
__declspec(dllimport) BOOL __stdcall CreateDirectoryA(const char* lpPathName, void* lpSecurityAttributes);

static void enable_ansi_terminal(void) {
    SetConsoleOutputCP(65001);
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut != (HANDLE)-1 && hOut != NULL) {
        DWORD dwMode = 0;
        if (GetConsoleMode(hOut, &dwMode)) {
            SetConsoleMode(hOut, dwMode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
        }
    }
}
#else
#include <unistd.h>
#define Sleep(ms) usleep((ms) * 1000)
#include <sys/stat.h>
static void enable_ansi_terminal(void) { }
#endif

static void render_retro_purple_loading_bar(const char* label) {
    enable_ansi_terminal();
    printf("\n  \033[1;38;2;220;120;255m[*] %s\033[0m\n  ", label ? label : "Cryptographically Sealing Block...");

    const int bar_width = 44;
    for (int step = 1; step <= bar_width; ++step) {
        float t = (float)step / (float)bar_width;
        int r = (int)(110 + t * (255 - 110));
        int g = (int)(0   + t * (85  - 0));
        int b = (int)(160 + t * (255 - 160));

        printf("\033[38;2;%d;%d;%dm█\033[0m", r, g, b);
        fflush(stdout);
#ifdef _WIN32
        Sleep(22);
#endif
    }
    printf(" \033[1;38;2;255;160;255m[100%% IMMUTABLE]\033[0m\n\n");
    fflush(stdout);
}

static void trim_line(char* s);

static void get_device_identity_seed(uint8_t out_seed[32], bool is_receiver) {
    const char* env_var = is_receiver ? "BMD_RECEIVER_SEED" : "BMD_DEVICE_SEED";
    const char* env_seed = getenv(env_var);
    if (env_seed && strlen(env_seed) == 64) {
        if (bmd_hex_to_bin(env_seed, out_seed, 32)) return;
    }

    /* Check persistent file in ~/.bmd/ */
    const char* home = getenv("USERPROFILE");
    if (!home || home[0] == '\0') home = getenv("HOME");
    if (!home || home[0] == '\0') home = ".";

    char bmd_dir[1024];
    char key_file[1024];
    snprintf(bmd_dir, sizeof(bmd_dir), "%s\\.bmd", home);
    snprintf(key_file, sizeof(key_file), "%s\\.bmd\\%s_device.key", home, is_receiver ? "receiver" : "emitter");

#ifdef _WIN32
    CreateDirectoryA(bmd_dir, NULL);
#else
    mkdir(bmd_dir, 0700);
#endif

    FILE* f = fopen(key_file, "r");
    if (f) {
        char hex_buf[128] = {0};
        if (fgets(hex_buf, sizeof(hex_buf), f)) {
            trim_line(hex_buf);
            if (strlen(hex_buf) == 64 && bmd_hex_to_bin(hex_buf, out_seed, 32)) {
                fclose(f);
                return;
            }
        }
        fclose(f);
    }

    /* Deterministic derivation from hardware/device fingerprint */
    char fp[1024];
    const char* comp = getenv("COMPUTERNAME");
    const char* user = getenv("USERNAME");
    const char* arch = getenv("PROCESSOR_ARCHITECTURE");
    const char* role_tag = is_receiver ? "BMD_RECEIVER_DEVICE_SALT_v2.1" : "BMD_EMITTER_DEVICE_SALT_v2.1";
    snprintf(fp, sizeof(fp), "%s|%s|%s|%s", comp ? comp : "BMD_NODE", user ? user : "ROOT", arch ? arch : "X64", role_tag);

    char sha_hex[129];
    bmd_sha512_hex((const uint8_t*)fp, strlen(fp), sha_hex);
    bmd_hex_to_bin(sha_hex, out_seed, 32);

    /* Persist for consistency across sessions */
    FILE* wf = fopen(key_file, "w");
    if (wf) {
        char seed_hex[65];
        bmd_bin_to_hex(out_seed, 32, seed_hex);
        fprintf(wf, "%s\n", seed_hex);
        fclose(wf);
    }
}

static void print_banner(void) {
    enable_ansi_terminal();

    /* 12-line large stylized ASCII font with 24-bit TrueColor vertical magenta gradient (bottom to top) */
    static const struct {
        int r, g, b;
        const char* text;
    } banner_lines[12] = {
        {255, 230, 253, "  ██████╗ ██╗      ██████╗  ██████╗██╗  ██╗ ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗"},
        {255, 205, 250, "  ██╔══██╗██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██║  ██║██╔══██╗██║████╗  ██║"},
        {255, 175, 246, "  ██████╔╝██║     ██║   ██║██║     █████╔╝ ██║     ███████║███████║██║██╔██╗ ██║"},
        {255, 145, 242, "  ██╔══██╗██║     ██║   ██║██║     ██╔═██╗ ██║     ██╔══██║██╔══██║██║██║╚██╗██║"},
        {255, 115, 238, "  ██████╔╝███████╗╚██████╔╝╚██████╗██║  ██╗╚██████╗██║  ██║██║  ██║██║██║ ╚████║"},
        {248,  85, 230, "  ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝"},
        {238,  55, 220, "  ███╗   ███╗  █████╗  ██████╗ ██╗  ██╗██████╗   ██████╗ ██╗    ██╗███╗   ██╗  "},
        {222,  30, 210, "  ████╗ ████║ ██╔══██╗ ██╔══██╗██║ ██╔╝██╔══██╗ ██╔═══██╗██║    ██║████╗  ██║  "},
        {205,  15, 195, "  ██╔████╔██║ ███████║ ██████╔╝█████╔╝ ██║  ██║ ██║   ██║██║ █╗ ██║██╔██╗ ██║  "},
        {180,   0, 180, "  ██║╚██╔╝██║ ██╔══██║ ██╔══██╗██╔═██╗ ██║  ██║ ██║   ██║██║███╗██║██║╚██╗██║  "},
        {155,   0, 155, "  ██║ ╚═╝ ██║ ██║  ██║ ██║  ██║██║  ██╗██████╔╝ ╚██████╔╝╚███╔███╔╝██║ ╚████║  "},
        {130,   0, 130, "  ╚═╝     ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝   ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═══╝  "}
    };

    printf("\n");
    for (int i = 0; i < 12; ++i) {
        printf("\033[38;2;%d;%d;%dm%s\033[0m\n",
               banner_lines[i].r, banner_lines[i].g, banner_lines[i].b,
               banner_lines[i].text);
    }
    printf("\n");
    printf("\033[38;2;220;120;235m  ════ Immutable Protocol • C11 Engine Runtime v%d.%d.%d ════\033[0m\n",
           BMD_VERSION_MAJOR, BMD_VERSION_MINOR, BMD_VERSION_PATCH);
    printf("\033[38;2;170;90;200m  Single Source of Truth: Public Content, Cryptographically Locked Edit\033[0m\n\n");
}

static void print_help(void) {
    printf("================================================================================\n");
    printf("  BLOCKCHAIN MARKDOWN (.bmd) COMMAND REFERENCE MANUAL\n");
    printf("================================================================================\n\n");
    printf("DOCUMENT VIEWING & VERIFICATION:\n");
    printf("  bmd read <file.bmd>                   Render document natively (letter-sheet view)\n");
    printf("  bmd <file.bmd>                        Short form: immediately view document\n");
    printf("  bmd verify <file.bmd>                 Verify SHA-512 hash & Ed25519 signatures\n");
    printf("  bmd verify --json <file.bmd>          Same verification with JSON output\n");
    printf("  bmd inspect <file.bmd>                Full block metadata, hashes & signature cap\n\n");
    printf("DRAFTING & REDACT STUDIO:\n");
    printf("  bmd redact [file.bmd]                 Open terminal editor (create or edit draft)\n\n");
    printf("SIGNING & IMMUTABILITY:\n");
    printf("  bmd sign <file.bmd>                   Sign as Emitter in DRAFT mode (auto device key & SHA-512)\n");
    printf("  bmd compile <file.bmd>                Compile, freeze to immutable TRANSFER mode & seal\n");
    printf("  bmd cosign <file.bmd>                 Receiver co-signs (auto device key, if max_signatures >= 2)\n");
    printf("  bmd lock <file.bmd>                   Apply OS read-only attribute to file\n\n");
    printf("LEDGER AUDIT:\n");
    printf("  bmd audit <b1.bmd> [b2.bmd ...]       Audit cryptographic chain of custody\n\n");
    printf("EXPORTS & INTELLIGENT / INTELLECTUAL PROPERTY (IP):\n");
    printf("  bmd render <file.bmd> [out.html]      Export standalone zero-dependency HTML viewer\n");
    printf("  bmd --inject-property <dir> <bmd>     Inject IP (Intelligent Property) code bundle\n");
    printf("  bmd --extract-property <bmd> [--out]  Extract & decrypt IP assets from block\n");
    printf("  bmd --export-office <file.bmd>        Export structured JSON metadata for integrations\n\n");
    printf("SHELL & UTILITY:\n");
    printf("  bmd                                   Launch interactive BMD shell\n");
    printf("  /help, help, -h, --help               Display this command manual\n");
    printf("  exit, quit, q                         Exit the interactive shell\n\n");
    printf("================================================================================\n\n");
}

static void print_usage(const char* prog) {
    (void)prog;
    print_banner();
    print_help();
}

static void trim_line(char* s) {
    if (!s) return;
    /* Strip UTF-8 Byte Order Mark (BOM: 0xEF, 0xBB, 0xBF) if present */
    if ((unsigned char)s[0] == 0xEF && (unsigned char)s[1] == 0xBB && (unsigned char)s[2] == 0xBF) {
        memmove(s, s + 3, strlen(s + 3) + 1);
    }
    char* p = s;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
    if (p != s) memmove(s, p, strlen(p) + 1);
    size_t len = strlen(s);
    while (len > 0 && (s[len - 1] == ' ' || s[len - 1] == '\t' || s[len - 1] == '\r' || s[len - 1] == '\n')) {
        s[--len] = '\0';
    }
}

static void sanitize_path(char* path) {
    if (!path) return;
    trim_line(path);
    size_t len = strlen(path);
    if (len >= 2 && ((path[0] == '"' && path[len-1] == '"') || (path[0] == '\'' && path[len-1] == '\''))) {
        memmove(path, path + 1, len - 2);
        path[len - 2] = '\0';
        trim_line(path);
        len = strlen(path);
    }
    /* If path starts with "//" or "\\", test if stripping it helps find the file */
    if (len >= 2 && ((path[0] == '/' && path[1] == '/') || (path[0] == '\\' && path[1] == '\\'))) {
        FILE* test = fopen(path, "rb");
        if (test) {
            fclose(test);
        } else {
            char alt[1024];
            snprintf(alt, sizeof(alt), "%s", path + 2);
            FILE* test2 = fopen(alt, "rb");
            if (test2) {
                fclose(test2);
                memmove(path, path + 2, len - 1);
            }
        }
    }
}

static void resolve_bmd_path(const char* input_path, char* out_path, size_t out_sz) {
    if (!input_path || !out_path || out_sz == 0) return;

    char cleaned[1024];
    strncpy(cleaned, input_path, sizeof(cleaned) - 1);
    cleaned[sizeof(cleaned) - 1] = '\0';
    sanitize_path(cleaned);

    /* 1. Direct check in current working directory */
    FILE* f = fopen(cleaned, "rb");
    if (f) {
        fclose(f);
        strncpy(out_path, cleaned, out_sz - 1);
        out_path[out_sz - 1] = '\0';
        return;
    }

    /* Extract basename */
    const char* base = cleaned;
    for (const char* p = cleaned; *p; ++p) {
        if (*p == '/' || *p == '\\') base = p + 1;
    }

    /* Dynamic candidate root paths based on USERPROFILE */
    const char* user_profile = getenv("USERPROFILE");
    char up_orunex[512] = {0};
    char up_bmd_engine[512] = {0};
    char up_examples[512] = {0};
    if (user_profile) {
        snprintf(up_orunex, sizeof(up_orunex), "%s\\Downloads\\Project_Orunex\\", user_profile);
        snprintf(up_bmd_engine, sizeof(up_bmd_engine), "%s\\Downloads\\Project_Orunex\\bmd_engine\\", user_profile);
        snprintf(up_examples, sizeof(up_examples), "%s\\Downloads\\Project_Orunex\\bmd_engine\\examples\\", user_profile);
    }

    const char* prefixes[] = {
        "Downloads\\Project_Orunex\\",
        "Downloads\\Project_Orunex\\bmd_engine\\",
        "Downloads\\Project_Orunex\\bmd_engine\\examples\\",
        "C:\\Users\\Hp\\Downloads\\Project_Orunex\\",
        "C:\\Users\\Hp\\Downloads\\Project_Orunex\\bmd_engine\\",
        "C:\\Users\\Hp\\Downloads\\Project_Orunex\\bmd_engine\\examples\\",
        up_orunex,
        up_bmd_engine,
        up_examples,
        "bmd_engine\\",
        "bmd_engine\\examples\\",
        "examples\\",
        "..\\",
        "..\\bmd_engine\\",
        "..\\bmd_engine\\examples\\",
        "..\\examples\\",
        "..\\..\\",
        "..\\..\\bmd_engine\\",
        "..\\..\\bmd_engine\\examples\\"
    };

    /* 2. Try candidate prefixes with relative path */
    for (size_t i = 0; i < sizeof(prefixes)/sizeof(prefixes[0]); ++i) {
        if (!prefixes[i] || prefixes[i][0] == '\0') continue;
        char test_path[1024];
        snprintf(test_path, sizeof(test_path), "%s%s", prefixes[i], cleaned);
        f = fopen(test_path, "rb");
        if (f) {
            fclose(f);
            strncpy(out_path, test_path, out_sz - 1);
            out_path[out_sz - 1] = '\0';
            return;
        }
    }

    /* 3. Try candidate prefixes with basename */
    for (size_t i = 0; i < sizeof(prefixes)/sizeof(prefixes[0]); ++i) {
        if (!prefixes[i] || prefixes[i][0] == '\0') continue;
        char test_path[1024];
        snprintf(test_path, sizeof(test_path), "%s%s", prefixes[i], base);
        f = fopen(test_path, "rb");
        if (f) {
            fclose(f);
            strncpy(out_path, test_path, out_sz - 1);
            out_path[out_sz - 1] = '\0';
            return;
        }
    }

    /* Fallback to cleaned */
    strncpy(out_path, cleaned, out_sz - 1);
    out_path[out_sz - 1] = '\0';
}

static int lock_file_readonly(const char* filepath) {
    char clean[1024];
    resolve_bmd_path(filepath, clean, sizeof(clean));

    char cmd[1200];
    snprintf(cmd, sizeof(cmd), "attrib +R \"%s\" >nul 2>&1", clean);
    int res = system(cmd);
    if (res == 0) {
        printf("[+] Operating system read-only lock applied to: %s\n", clean);
        printf("    Direct file modification is now physically blocked by filesystem.\n");
    }
    return res;
}

static void unlock_file_writable(const char* filepath) {
    char clean[1024];
    resolve_bmd_path(filepath, clean, sizeof(clean));
    char cmd[1200];
    snprintf(cmd, sizeof(cmd), "attrib -R \"%s\" >nul 2>&1", clean);
    system(cmd);
}

static int cmd_inspect(const char* filepath) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] Error loading file '%s': %s\n", clean_path, bmd_status_string(st));
        return 1;
    }

    bmd_status_t v_st = bmd_verify_document(doc);

    if (doc->header.block_id[0] != '\0') {
        printf("\n--- BLOCK METADATA [%s] ---\n", doc->header.block_id);
    } else {
        printf("\n--- BLOCKCHAIN DOCUMENT METADATA ---\n");
    }
    printf("  Document Type       : %s\n", doc->header.document_type[0] ? doc->header.document_type : "unspecified");
    printf("  Previous Hash       : %s\n", doc->header.previous_hash);
    printf("  Current Hash        : %s\n", doc->header.current_hash);
    printf("  Computed Hash       : %s\n", doc->computed_hash);
    printf("  Operational Mode    : %s (%s)\n", bmd_mode_string(doc->header.mode),
           doc->header.mode == BMD_MODE_TRANSFER ? "FROZEN EDITING / IMMUTABLE" : "MUTABLE DRAFT");
    printf("  Signer Role         : %s\n", (doc->header.signer_role == BMD_ROLE_EMISOR) ? "emitter" : (doc->header.signer_role == BMD_ROLE_RECEPTOR) ? "receiver" : "unspecified");
    printf("  Timestamp           : %lld\n", (long long)doc->header.timestamp);
    printf("  Emitter Public Key  : %s\n", doc->header.public_key[0] ? doc->header.public_key : "(none)");
    printf("  Emitter Signature   : %s\n", doc->header.signature_layer_2[0] ? doc->header.signature_layer_2 : "(none)");
    printf("  Receiver Public Key : %s\n", doc->header.receiver_public_key[0] ? doc->header.receiver_public_key : "(none)");
    printf("  Receiver Signature  : %s\n", doc->header.receiver_signature[0] ? doc->header.receiver_signature : "(none)");
    if (doc->header.property_bundle_hash[0] != '\0') {
        printf("  IP Bundle Hash      : %s\n", doc->header.property_bundle_hash);
        printf("  IP Bundle Size      : %llu bytes\n", (unsigned long long)doc->header.property_bundle_size);
        printf("  Source Destroyed    : %s\n", doc->header.property_bundle_destroyed ? "YES (True Ownership Transfer)" : "NO");
    }
    if (doc->header.max_signatures > 0) {
        int current_sigs = (doc->header.signature_layer_2[0] != '\0') ? 1 : 0;
        if (doc->header.receiver_signature[0] != '\0') current_sigs++;
        printf("  Max Signatures      : %d (current: %d / %d)\n",
               doc->header.max_signatures, current_sigs, doc->header.max_signatures);
        if (current_sigs >= doc->header.max_signatures) {
            printf("  Signature Cap       : REACHED — Co-signature rejected\n");
        } else {
            printf("  Signature Cap       : Open (%d slot(s) remaining)\n",
               doc->header.max_signatures - current_sigs);
        }
    }
    printf("  Validation Status   : %s\n", v_st == BMD_OK ? "[VALID - AUTHENTIC CONTENT]" : "[INVALID - TAMPER DETECTED]");
    if (v_st != BMD_OK) {
        printf("  Failure Detail      : %s\n", bmd_status_string(v_st));
    }

    printf("\n--- PAYLOAD EXCERPT (First 250 characters) ---\n");
    if (doc->payload) {
        char excerpt[251];
        strncpy(excerpt, doc->payload, 250);
        excerpt[250] = '\0';
        printf("%s%s\n\n", excerpt, strlen(doc->payload) > 250 ? "..." : "");
    }

    bmd_document_free(doc);
    return (v_st == BMD_OK) ? 0 : 2;
}

static int cmd_verify(const char* filepath) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] Error loading file '%s': %s\n", clean_path, bmd_status_string(st));
        return 1;
    }

    st = bmd_verify_document(doc);
    if (st == BMD_OK) {
        if (doc->header.block_id[0] != '\0') {
            printf("[+] VERIFICATION SUCCESS: Block '%s' is authentic and unmodified.\n", doc->header.block_id);
        } else {
            printf("[+] VERIFICATION SUCCESS: Document (SHA-512: %.16s...) is authentic and unmodified.\n", doc->header.current_hash);
        }
        bmd_document_free(doc);
        return 0;
    } else {
        if (doc->header.block_id[0] != '\0') {
            fprintf(stderr, "[-] SECURITY BREACH in '%s': %s\n", doc->header.block_id, bmd_status_string(st));
        } else {
            fprintf(stderr, "[-] SECURITY BREACH (SHA-512: %.16s...): %s\n", doc->header.current_hash, bmd_status_string(st));
        }
        bmd_document_free(doc);
        return 2;
    }
}

static int cmd_verify_json(const char* filepath) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\",\"hash_valid\":false,\"current_state\":\"unreadable\"}\n", bmd_status_string(st));
        return 1;
    }

    st = bmd_verify_document(doc);
    bool hash_valid = (st == BMD_OK);
    const char* state_str = "draft";
    if (doc->header.mode == BMD_MODE_TRANSFER) {
        if (doc->header.receiver_signature[0] != '\0') {
            state_str = "dual_signed";
        } else {
            state_str = "compiled_transfer";
        }
    }

    printf("{\"status\":\"%s\",\"error\":\"%s\",\"hash_valid\":%s,\"current_state\":\"%s\",\"block_id\":\"%s\",\"document_type\":\"%s\",\"current_hash\":\"%s\",\"computed_hash\":\"%s\",\"signer_role\":\"%s\",\"emitter_pubkey\":\"%s\",\"emitter_signature\":\"%s\",\"receiver_pubkey\":\"%s\",\"receiver_signature\":\"%s\",\"has_property_bundle\":%s}\n",
           hash_valid ? "ok" : "tampered",
           hash_valid ? "none" : bmd_status_string(st),
           hash_valid ? "true" : "false",
           state_str,
           doc->header.block_id,
           doc->header.document_type,
           doc->header.current_hash,
           doc->computed_hash,
           bmd_role_string(doc->header.signer_role),
           doc->header.public_key,
           doc->header.signature_layer_2,
           doc->header.receiver_public_key,
           doc->header.receiver_signature,
           (doc->header.property_bundle_hash[0] != '\0') ? "true" : "false");

    bmd_document_free(doc);
    return hash_valid ? 0 : 2;
}

static int cmd_compile_sign(const char* filepath, const char* seed_opt) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    uint8_t seed[32];
    if (seed_opt && strlen(seed_opt) == 64) {
        bmd_hex_to_bin(seed_opt, seed, 32);
    } else {
        const char* default_seed_hex = "4242424242424242424242424242424242424242424242424242424242424242";
        bmd_hex_to_bin(default_seed_hex, seed, 32);
    }

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\"}\n", bmd_status_string(st));
        return 1;
    }

    st = bmd_transition_to_transfer(doc, seed);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\"}\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 2;
    }

    unlock_file_writable(clean_path);
    st = bmd_save_file(doc, clean_path);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\"}\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 3;
    }

    printf("{\"status\":\"ok\",\"action\":\"compile_sign\",\"block_id\":\"%s\",\"current_hash\":\"%s\",\"mode\":\"transfer\",\"public_key\":\"%s\",\"signature\":\"%s\"}\n",
           doc->header.block_id,
           doc->header.current_hash,
           doc->header.public_key,
           doc->header.signature_layer_2);

    lock_file_readonly(clean_path);
    bmd_document_free(doc);
    return 0;
}

static int cmd_sign(const char* filepath, const char* seed_hex) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    uint8_t seed[32];
    if (seed_hex && strlen(seed_hex) == 64) {
        bmd_hex_to_bin(seed_hex, seed, 32);
    } else {
        /* Automatic device signature */
        get_device_identity_seed(seed, false);
    }

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] Error loading '%s': %s\n", clean_path, bmd_status_string(st));
        return 1;
    }

    if (doc->header.mode == BMD_MODE_TRANSFER) {
        fprintf(stderr, "[-] Document is already sealed in TRANSFER mode and cannot be modified.\n");
        bmd_document_free(doc);
        return 2;
    }

    printf("[+] Computing SHA-512 payload hash automatically...\n");
    printf("[+] Digitally signing as Emitter with authenticated device key...\n");
    st = bmd_sign_document(doc, seed, BMD_ROLE_EMISOR);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] Sign failed: %s\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 2;
    }

    /* Note: mode remains DRAFT (not frozen yet until compile!) */
    unlock_file_writable(clean_path);
    unlock_file_writable(clean_path);
    st = bmd_save_file(doc, clean_path);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] File save failed: %s\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 3;
    }

    printf("[+] DOCUMENT SIGNED AS EMITTER (DRAFT MODE):\n");
    if (doc->header.block_id[0] != '\0') {
        printf("    Block ID     : %s\n", doc->header.block_id);
    }
    printf("    SHA-512 Hash : %.64s\n", doc->header.current_hash);
    printf("                 : %.64s\n", doc->header.current_hash + 64);
    printf("    Public Key   : %s\n", doc->header.public_key);
    printf("    Signature    : %.64s...\n", doc->header.signature_layer_2);
    printf("    Mode         : DRAFT (Mutable — Ready for 'bmd compile' to seal)\n");
    printf("    File         : %s\n", clean_path);

    bmd_document_free(doc);
    return 0;
}

static int cmd_compile(const char* filepath, const char* seed_hex) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    uint8_t seed[32];
    if (seed_hex && strlen(seed_hex) == 64) {
        bmd_hex_to_bin(seed_hex, seed, 32);
    } else {
        /* Automatic device signature */
        get_device_identity_seed(seed, false);
    }

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] Error loading '%s': %s\n", clean_path, bmd_status_string(st));
        return 1;
    }

    if (doc->header.mode == BMD_MODE_TRANSFER) {
        fprintf(stderr, "[-] Document is already sealed in TRANSFER mode.\n");
        bmd_document_free(doc);
        return 0;
    }

    /* Retro purple pixel loading bar animation! */
    render_retro_purple_loading_bar("Cryptographically Compiling & Sealing Block...");

    /* Freeze to transfer mode */
    st = bmd_transition_to_transfer(doc, seed);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] Compile failed: %s\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 2;
    }

    unlock_file_writable(clean_path);
    st = bmd_save_file(doc, clean_path);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] File save failed: %s\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 3;
    }

    lock_file_readonly(clean_path);

    printf("[+] DOCUMENT COMPILED & FROZEN IN TRANSFER MODE (IMMUTABLE):\n");
    if (doc->header.block_id[0] != '\0') {
        printf("    Block ID     : %s\n", doc->header.block_id);
    }
    printf("    SHA-512 Hash : %.64s\n", doc->header.current_hash);
    printf("                 : %.64s\n", doc->header.current_hash + 64);
    printf("    Public Key   : %s\n", doc->header.public_key);
    printf("    Signature    : %.64s...\n", doc->header.signature_layer_2);
    printf("    Mode         : TRANSFER (IMMUTABLE SEALED)\n");
    printf("    Disk Status  : Read-only locked (tamper-proof)\n");
    printf("    File         : %s\n", clean_path);

    bmd_document_free(doc);
    return 0;
}

static int cmd_cosign(const char* filepath, const char* seed_opt) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    uint8_t seed[32];
    if (seed_opt && strlen(seed_opt) == 64) {
        bmd_hex_to_bin(seed_opt, seed, 32);
    } else {
        /* Automatic receiver device signature */
        get_device_identity_seed(seed, true);
    }

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\"}\n", bmd_status_string(st));
        return 1;
    }

    if (doc->header.signature_layer_2[0] == '\0') {
        fprintf(stderr, "[-] Document must be signed by Emitter before co-signing.\n");
        bmd_document_free(doc);
        return 2;
    }

    if (doc->header.max_signatures < 2) {
        fprintf(stderr, "[-] Co-sign rejected: max_signatures = %d (Unilateral document).\n", doc->header.max_signatures);
        bmd_document_free(doc);
        return 2;
    }

    st = bmd_cosign_receiver(doc, seed);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\"}\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 2;
    }

    unlock_file_writable(clean_path);
    st = bmd_save_file(doc, clean_path);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\"}\n", bmd_status_string(st));
        bmd_document_free(doc);
        return 3;
    }

    printf("{\"status\":\"ok\",\"action\":\"co_sign\",\"current_hash\":\"%s\",\"receiver_pubkey\":\"%s\",\"receiver_signature\":\"%s\"}\n",
           doc->header.current_hash,
           doc->header.receiver_public_key,
           doc->header.receiver_signature);

    lock_file_readonly(clean_path);
    bmd_document_free(doc);
    return 0;
}

static void resolve_python_script(const char* script_name, char* out_path, size_t max_len) {
    const char* home = getenv("USERPROFILE");
    if (!home || home[0] == '\0') home = getenv("HOME");

    char p_home[1024] = {0};
    char p_dl[1024]   = {0};
    char p_apps[1024] = {0};
    if (home) {
        snprintf(p_home, sizeof(p_home), "%s\\.bmd\\python\\%s", home, script_name);
        snprintf(p_dl,   sizeof(p_dl),   "%s\\Downloads\\Project_Orunex\\bmd_engine\\python\\%s", home, script_name);
    }
    const char* localapp = getenv("LOCALAPPDATA");
    if (localapp) {
        snprintf(p_apps, sizeof(p_apps), "%s\\Microsoft\\WindowsApps\\python\\%s", localapp, script_name);
    }

    const char* candidates[] = {
        p_home,
        p_dl,
        p_apps,
        "bmd_engine\\python\\",
        "python\\",
        "..\\python\\",
        "..\\..\\python\\",
        ""
    };
    for (size_t i = 0; i < sizeof(candidates)/sizeof(candidates[0]); ++i) {
        if (!candidates[i] || candidates[i][0] == '\0') continue;
        if (strchr(candidates[i], '\\') && (candidates[i][1] == ':' || candidates[i][0] == '\\')) {
            /* Absolute path already */
            snprintf(out_path, max_len, "%s", candidates[i]);
        } else {
            snprintf(out_path, max_len, "%s%s", candidates[i], script_name);
        }
        FILE* f = fopen(out_path, "r");
        if (f) {
            fclose(f);
            return;
        }
    }
    if (p_home[0]) {
        snprintf(out_path, max_len, "%s", p_home);
    } else {
        snprintf(out_path, max_len, "bmd_engine\\python\\%s", script_name);
    }
}

static int cmd_inject_property_forward(const char* dirpath, const char* bmdpath) {
    char script_path[1024];
    resolve_python_script("bmd_property.py", script_path, sizeof(script_path));
    char cmd_buf[2048];
    snprintf(cmd_buf, sizeof(cmd_buf), "python \"%s\" --inject \"%s\" --bmd \"%s\"", script_path, dirpath, bmdpath);
    return system(cmd_buf);
}

static int cmd_extract_property_forward(const char* bmdpath, const char* outdir) {
    char script_path[1024];
    resolve_python_script("bmd_property.py", script_path, sizeof(script_path));
    char cmd_buf[2048];
    snprintf(cmd_buf, sizeof(cmd_buf), "python \"%s\" --extract \"%s\" --out \"%s\"", script_path, bmdpath, outdir ? outdir : "./extracted_ip");
    return system(cmd_buf);
}

static int cmd_render_forward(const char* bmdpath, const char* outpath) {
    char script_path[1024];
    resolve_python_script("bmd_viewer_generator.py", script_path, sizeof(script_path));
    char cmd_buf[2048];
    if (outpath) {
        snprintf(cmd_buf, sizeof(cmd_buf), "python \"%s\" \"%s\" \"%s\"", script_path, bmdpath, outpath);
    } else {
        snprintf(cmd_buf, sizeof(cmd_buf), "python \"%s\" \"%s\"", script_path, bmdpath);
    }
    return system(cmd_buf);
}

/* ================================================================
   REDACT: FULL TERMINAL STUDIO
   ================================================================ */

#define REDACT_MAX_LINES 512
#define REDACT_LINE_CAP  1024

typedef struct {
    char block_id[256];
    char document_type[128];
    char jurisdiction[256];
    int  max_signatures;
    char emitter_pubkey[256];
    char emitter_sig[256];
    char receiver_pubkey[256];
    char receiver_sig[256];
    char current_hash[256];
    int  mode_transfer;
    char property_bundle_hash[129];
    uint64_t property_bundle_size;
    bool property_bundle_destroyed;
} redact_meta_t;

typedef struct {
    char         lines[REDACT_MAX_LINES][REDACT_LINE_CAP];
    int          count;
    redact_meta_t meta;
    char         filename[1024];
    int          modified;
    int          compiled;
    char*        bundle_data;
    size_t       bundle_data_len;
} redact_buf_t;

static const char* REDACT_MANUAL =
"\n"
"  ================================================================================\n"
"   BMD REDACT STUDIO  -  COMPLETE REFERENCE MANUAL\n"
"  ================================================================================\n"
"\n"
"  WHAT IS BLOCKCHAIN MARKDOWN?\n"
"  A .bmd file is a cryptographically sealed document. Once compiled, no byte\n"
"  of its payload may be altered without breaking the SHA-512 ledger hash and\n"
"  Ed25519 digital signatures. Document uniqueness and custody are anchored\n"
"  in cryptographic math (SHA-512 and Ed25519) rather than arbitrary block IDs,\n"
"  making forged or spoofed document IDs impossible. The canonical truth lives\n"
"  in the .bmd file; any HTML export is purely a rendering view layer.\n"
"\n"
"  GENERAL WORKFLOW\n"
"  1. Open the studio (from the BMD shell or terminal):\n"
"       bmd redact                         open blank new document\n"
"       bmd redact my_contract.bmd         open existing file\n"
"  2. Set frontmatter metadata with :set (e.g. :set type contract)\n"
"  3. Write content lines with :add <tag> text\n"
"  4. Insert signature buttons: :add sign_button  (and :add cosign_button for 2 parties)\n"
"  5. Preview the clean document with :preview\n"
"  6. Save the draft with :save <filename.bmd>\n"
"  7. Sign as Emitter with :sign\n"
"       (Uses your authentic device SHA-512/Ed25519 identity key automatically.\n"
"        Leaves document in DRAFT mode so you can continue editing if needed.)\n"
"  8. When ready to seal forever, run :compile\n"
"       (Displays retro purple pixel animation, locks document into TRANSFER mode,\n"
"        and applies OS filesystem read-only lock attribute.)\n"
"  9. If max_signatures >= 2, the Receiver co-signs with :cosign\n"
"       (Uses Receiver device identity key automatically; reaches CONSENSUS RATIFIED.)\n"
" 10. Export an HTML viewer with :render [output.html]\n"
" 11. Verify integrity at any time with :verify\n"
"\n"
"  -------------------------\n"
"  CONTENT TAGS & BUTTON DIRECTIVES\n"
"  -------------------------\n"
"  <title>Your Title Text</title>\n"
"      Document-level title. Rendered large and centered.\n"
"      Example:  :add <title>Service Agreement 2026</title>\n"
"\n"
"  <subtitle>Your Subtitle</subtitle>\n"
"      Secondary title or description line.\n"
"      Example:  :add <subtitle>Between Acme Corp and Client LLC</subtitle>\n"
"\n"
"  <heading>Section Name</heading>\n"
"      Section heading. Displayed with === delimiters in terminal.\n"
"      Example:  :add <heading>Terms and Conditions</heading>\n"
"\n"
"  <body>Paragraph text here.</body>\n"
"      Standard body paragraph text. Long lines word-wrap automatically.\n"
"      Example:  :add <body>Provider agrees to deliver software on schedule.</body>\n"
"\n"
"  <bmd:sign_button>   (or shortcut: :add sign_button)\n"
"      Interactive Emitter signature button directive.\n"
"      Shows pending status in draft, displays verified pubkey when signed.\n"
"\n"
"  <bmd:cosign_button> (or shortcut: :add cosign_button)\n"
"      Interactive Receiver co-signature button directive.\n"
"      Automatically sets max_signatures = 2.\n"
"\n"
"  <bmd:rule>\n"
"      Renders a double horizontal rule separator (=====) across the page.\n"
"\n"
"  <bmd:rule single>\n"
"      Renders a single horizontal rule separator (-----) across the page.\n"
"\n"
"  <bmd:parties>\n"
"      Renders the Emitter and Receiver public key side-by-side table.\n"
"\n"
"  <bmd:signatures>\n"
"      Renders the formal Ed25519 signature verification panel for both parties.\n"
"\n"
"  <bmd:seal>\n"
"      Renders the final cryptographic custody seal line.\n"
"\n"
"  -------------------------\n"
"  FRONTMATTER FIELDS  (:set command)\n"
"  -------------------------\n"
"  type              Document category (contract, declaration, license, invoice, agreement...)\n"
"                    Example:  :set type contract\n"
"\n"
"  jurisdiction      Legal jurisdiction (e.g. International, Delaware, Mexico, Open Standard)\n"
"                    Example:  :set jurisdiction International\n"
"\n"
"  max_signatures    Required signatures (1 = Unilateral, 2 = Bilateral counter-party)\n"
"                    Example:  :set max_signatures 2\n"
"\n"
"  block_id          (Optional) Optional legacy label; not required for integrity.\n"
"\n"
"  -------------------------\n"
"  ALL STUDIO COMMANDS\n"
"  -------------------------\n"
"  :help                        Show this reference manual\n"
"  :add <tag> text              Append a tagged content line\n"
"  :add sign_button             Insert Emitter signature button (<bmd:sign_button>)\n"
"  :add cosign_button           Insert Receiver co-sign button (<bmd:cosign_button>)\n"
"  :insert <N> <tag> text       Insert tagged line before line N (1-based)\n"
"  :delete <N>                  Delete line N\n"
"  :set <field> <value>         Set frontmatter (type, jurisdiction, max_signatures)\n"
"  :list                        Show complete numbered line listing\n"
"  :preview                     Show clean document preview (tags rendered)\n"
"  :save [filename.bmd]         Save draft to disk\n"
"  :inject [path]               Inject & encrypt codebase/folder into document\n"
"  :extract [dir]               Extract & decrypt IP codebase from document\n"
"  :sign                        Sign as Emitter with auto device key (keeps in DRAFT)\n"
"  :compile                     Retro purple animation, freeze to TRANSFER & seal disk\n"
"  :cosign                      Co-sign as Receiver with auto device key\n"
"  :render [output.html]        Export standalone HTML viewer\n"
"  :verify                      Cryptographically verify saved file\n"
"  :inspect                     Show block metadata summary\n"
"  :read <file.bmd>             Open another .bmd file\n"
"  :up  :down  :top  :bottom    Scroll the document view\n"
"  :quit  :q  :exit             Exit editor (warns if unsaved changes exist)\n"
"  :quit!  :q!                  Force quit without saving\n"
"\n"
"  ================================================================================\n"
"\n";

static void redact_clear_screen(void) {
    printf("\033[2J\033[H");
    fflush(stdout);
}

/* Forward declarations — defined later in the file, before cmd_view */
static void print_sheet_title(const char* text);
static void print_sheet_subtitle(const char* text);
static void print_sheet_heading(const char* text);
static void print_sheet_line(const char* text);

/* Print a single-line button label padded to fixed width */
static void redact_btn(const char* label, int width) {
    int llen = (int)strlen(label);
    int pad  = (width - llen - 4);
    if (pad < 0) pad = 0;
    printf("[ %s%*s]", label, pad, "");
}

static void redact_draw(redact_buf_t* buf, int scroll_top) {
    redact_clear_screen();

    const char* mode_str = buf->compiled ? "TRANSFER (IMMUTABLE)" : "DRAFT (MUTABLE)";
    const char* fname    = buf->filename[0] ? buf->filename : "(unsaved)";
    const char* mflag    = buf->modified    ? " [modified]"  : "";

    printf("\n  ================================================================================\n");
    printf("   BMD REDACT STUDIO  |  %s%s  |  mode: %s\n", fname, mflag, mode_str);
    printf("  ================================================================================\n\n");

    /* Frontmatter summary */
    printf("  Frontmatter:\n");
    if (buf->meta.block_id[0]) {
        printf("    block_id        : %s\n", buf->meta.block_id);
    }
    printf("    type            : %s\n",
           buf->meta.document_type[0] ? buf->meta.document_type : "(not set  ->  :set type declaration)");
    printf("    jurisdiction    : %s\n",
           buf->meta.jurisdiction[0] ? buf->meta.jurisdiction : "(not set  ->  :set jurisdiction International)");
    printf("    max_signatures  : %d  %s\n",
           buf->meta.max_signatures,
           buf->meta.max_signatures <= 1
               ? "(unilateral - Emitter only)"
               : "(bilateral  - requires Emitter + Receiver)");

    /* Signature status indicators */
    printf("    emitter_sig     : ");
    if (buf->meta.emitter_sig[0]) {
        printf("[SIGNED]  pubkey: %.48s...\n", buf->meta.emitter_pubkey);
    } else {
        printf("[UNSIGNED - ready for :sign]\n");
    }
    if (buf->meta.max_signatures >= 2) {
        printf("    receiver_sig    : ");
        if (buf->meta.receiver_sig[0]) {
            printf("[CO-SIGNED]  pubkey: %.44s...\n", buf->meta.receiver_pubkey);
        } else {
            printf("[AWAITING CO-SIGNATURE]\n");
        }
    }
    /* Show hash if computed */
    if (buf->meta.current_hash[0]) {
        printf("    SHA-512 hash    : %.64s\n", buf->meta.current_hash);
        printf("                      %.64s\n", buf->meta.current_hash + 64);
    } else {
        printf("    SHA-512 hash    : (computed automatically on :sign or :compile)\n");
    }
    if (buf->meta.property_bundle_hash[0] != '\0') {
        printf("    IP Bundle       : %llu bytes encrypted (ChaCha20) | SHA-256: %.20s...\n",
               (unsigned long long)buf->meta.property_bundle_size,
               buf->meta.property_bundle_hash);
        printf("    IP Custody      : %s\n",
               buf->meta.property_bundle_destroyed ? "OWNERSHIP TRANSFERRED (source moved into block)" : "INJECTED");
    }
    printf("\n");

    /* Document content */
    int total = buf->count;
    printf("  Document  (%d line%s):\n", total, total == 1 ? "" : "s");
    printf("  +--------+--------------------------------------------------------------------+\n");
    printf("  |  Line  |  Content                                                           |\n");
    printf("  +--------+--------------------------------------------------------------------+\n");

    int visible = 14;
    int end = scroll_top + visible;
    if (end > total) end = total;

    if (total == 0) {
        printf("  |        |  (empty - use :add <tag> text  or  :help to see the manual)       |\n");
    } else {
        for (int i = scroll_top; i < end; i++) {
            char ex[69];
            strncpy(ex, buf->lines[i], 68);
            ex[68] = '\0';
            printf("  | %6d | %-68s |\n", i + 1, ex);
        }
        if (total > end) {
            int remaining = total - end;
            printf("  |   ...  |  (%d more line%s - :down to scroll, :list to see all)%*s|\n",
                   remaining, remaining == 1 ? "" : "s",
                   (int)(remaining < 10 ? 20 : remaining < 100 ? 19 : 18), "");
        }
    }
    printf("  +--------+--------------------------------------------------------------------+\n\n");

    /* --------------------------------------------------------
       ACTION BUTTONS BAR
       -------------------------------------------------------- */
    printf("  ================================================================================\n");

    if (!buf->compiled) {
        /* DRAFT MODE */
        printf("  ACTIONS:\n");
        printf("  +-----------------------------+  +-----------------------------+\n");
        printf("  |  :sign                      |  |  :compile                   |\n");
        printf("  |  Sign with auto device key  |  |  Retro purple loading bar   |\n");
        printf("  |  (remains in DRAFT mode)    |  |  Freeze to IMMUTABLE mode   |\n");
        printf("  +-----------------------------+  +-----------------------------+\n\n");
        printf("  BUTTONS:  :add sign_button   :add cosign_button   :add extract_button\n");
        printf("  IP ASSET: :inject <path>     (encrypts folder & embeds into block)\n");
        printf("  CONTENT:  :add <tag> text   :insert N <tag> text   :delete N   :set <field> <val>\n");
        printf("  UTILITY:  :save [file]  :preview  :list  :verify  :render  :help  :quit\n");
        if (buf->meta.max_signatures >= 2 && buf->meta.emitter_sig[0] && !buf->meta.receiver_sig[0]) {
            printf("\n  +-------------------------------------------------------------+\n");
            printf("  |  :cosign                       (Receiver auto co-signs to ratify) |\n");
            printf("  +-------------------------------------------------------------+\n");
        }
    } else {
        /* IMMUTABLE MODE */
        int sigs = (buf->meta.emitter_sig[0] ? 1 : 0) + (buf->meta.receiver_sig[0] ? 1 : 0);
        int cap  = buf->meta.max_signatures > 0 ? buf->meta.max_signatures : 1;
        printf("  [IMMUTABLE]  Signatures: %d / %d  |  SHA-512 hash locked\n", sigs, cap);
        if (buf->meta.max_signatures >= 2 && buf->meta.emitter_sig[0] && !buf->meta.receiver_sig[0]) {
            printf("\n  +-------------------------------------------------------------+\n");
            printf("  |  :cosign                       (Receiver auto co-signs to ratify) |\n");
            printf("  +-------------------------------------------------------------+\n");
        } else if (sigs >= cap) {
            printf("  [CONSENSUS RATIFIED]  Signature cap reached. Document is fully sealed.\n");
        }
        printf("\n  Available: :cosign  :extract [dir]  :render [out.html]  :verify  :inspect  :quit\n");
    }
    printf("  ================================================================================\n\n");
}

static void redact_show_preview(redact_buf_t* buf) {
    redact_clear_screen();
    printf("\n  +----------------------------------------------------------------------------+\n");
    printf("  |  PREVIEW  -  Clean Document View (tags hidden)                             |\n");
    printf("  +----------------------------------------------------------------------------+\n");
    printf("  |                                                                            |\n");

    for (int i = 0; i < buf->count; i++) {
        const char* raw = buf->lines[i];
        char clean[1024] = {0};

        if (strstr(raw, "<bmd:sign_button>") || strstr(raw, ":add sign_button")) {
            if (buf->meta.emitter_sig[0]) {
                printf("  |  +------------------------------------------------------------------+  |\n");
                printf("  |  |  [v SIGNED AS EMITTER]  Ed25519 Verified      (sealed)            |  |\n");
                printf("  |  +------------------------------------------------------------------+  |\n");
            } else {
                printf("  |  +------------------------------------------------------------------+  |\n");
                printf("  |  |  [ SIGN AS EMITTER ]   SHA-512 auto-computed  (run :sign)        |  |\n");
                printf("  |  +------------------------------------------------------------------+  |\n");
            }
            continue;
        }
        if (strstr(raw, "<bmd:cosign_button>") || strstr(raw, ":add cosign_button")) {
            if (buf->meta.receiver_sig[0]) {
                printf("  |  +------------------------------------------------------------------+  |\n");
                printf("  |  |  [v CO-SIGNED BY RECEIVER]  Ed25519 Ratified  (sealed)            |  |\n");
                printf("  |  +------------------------------------------------------------------+  |\n");
            } else {
                printf("  |  +------------------------------------------------------------------+  |\n");
                printf("  |  |  [ CO-SIGN AS RECEIVER ]  SHA-512 auto-computed  (run :cosign)   |  |\n");
                printf("  |  +------------------------------------------------------------------+  |\n");
            }
            continue;
        }
        if (strstr(raw, "<bmd:extract_button>") || strstr(raw, ":add extract_button")) {
            if (buf->meta.property_bundle_hash[0] != '\0' || buf->bundle_data) {
                printf("  |  +------------------------------------------------------------------+  |\n");
                printf("  |  |  [v EXTRACT INTELLIGENT PROPERTY] ChaCha20 Sealed (run :extract) |  |\n");
                printf("  |  +------------------------------------------------------------------+  |\n");
            } else {
                printf("  |  +------------------------------------------------------------------+  |\n");
                printf("  |  |  [ EXTRACT INTELLIGENT PROPERTY ] (No IP bundle attached)        |  |\n");
                printf("  |  +------------------------------------------------------------------+  |\n");
            }
            continue;
        }
        if (strstr(raw, "<bmd:rule")) {
            printf("  |  ======================================================================  |\n");
            continue;
        }
        if (strstr(raw, "<bmd:parties>")) {
            printf("  |  [ Emitter public key ]  |  [ Receiver public key ]                     |\n");
            continue;
        }
        if (strstr(raw, "<bmd:signatures>")) {
            printf("  |  [ Emitter signature ]   |  [ Receiver co-signature ]                   |\n");
            continue;
        }
        if (strstr(raw, "<bmd:seal>")) {
            printf("  |  [*] BLOCKCHAIN MARKDOWN CRYPTOGRAPHIC CUSTODY SEAL: SHA-512 VERIFIED   |\n");
            continue;
        }
        if (raw[0] == '\0') {
            printf("  |                                                                            |\n");
            continue;
        }

        /* Extract text from typography tags */
        const char* tags[] = {"title", "subtitle", "heading", "body", NULL};
        int handled = 0;
        for (int t = 0; tags[t]; t++) {
            char open_tag[32], close_tag[32];
            snprintf(open_tag,  sizeof(open_tag),  "<%s>", tags[t]);
            snprintf(close_tag, sizeof(close_tag), "</%s>", tags[t]);
            char* s1 = strstr((char*)raw, open_tag);
            if (s1) {
                s1 += strlen(open_tag);
                char* s2 = strstr(s1, close_tag);
                size_t len = s2 ? (size_t)(s2 - s1) : strlen(s1);
                if (len >= sizeof(clean)) len = sizeof(clean) - 1;
                memcpy(clean, s1, len);
                clean[len] = '\0';
                if (strcmp(tags[t], "title") == 0) {
                    print_sheet_title(clean);
                } else if (strcmp(tags[t], "subtitle") == 0) {
                    print_sheet_subtitle(clean);
                } else if (strcmp(tags[t], "heading") == 0) {
                    print_sheet_heading(clean);
                } else {
                    print_sheet_line(clean);
                }
                handled = 1;
                break;
            }
        }
        /* Markdown heading fallbacks */
        if (!handled) {
            if (strncmp(raw, "# ", 2) == 0) {
                print_sheet_title(raw + 2);
                handled = 1;
            } else if (strncmp(raw, "## ", 3) == 0) {
                print_sheet_subtitle(raw + 3);
                handled = 1;
            } else if (strncmp(raw, "### ", 4) == 0) {
                print_sheet_heading(raw + 4);
                handled = 1;
            }
        }
        if (!handled) {
            print_sheet_line(raw);
        }
    }

    printf("  |                                                                            |\n");
    printf("  +----------------------------------------------------------------------------+\n");
    printf("\n  Press ENTER to return to editor.\n");
    char tmp[8];
    fgets(tmp, sizeof(tmp), stdin);
}

static int redact_save_bmd(redact_buf_t* buf, const char* path) {
    if (!path || path[0] == '\0') {
        if (buf->filename[0] == '\0') {
            printf("  [-] No filename set. Use:  :save <filename.bmd>\n");
            return 1;
        }
        path = buf->filename;
    }

    unlock_file_writable(path);

    FILE* f = fopen(path, "wb");
    if (!f) {
        printf("  [-] Cannot open '%s' for writing.\n", path);
        return 1;
    }

    fprintf(f, "---\n");
    fprintf(f, "bmd_version: 2.1\n");
    if (buf->meta.block_id[0])         fprintf(f, "block_id: %s\n",             buf->meta.block_id);
    fprintf(f, "document_type: %s\n",  buf->meta.document_type[0]  ? buf->meta.document_type  : "document");
    fprintf(f, "mode: %s\n",           buf->meta.mode_transfer      ? "transfer"               : "draft");
    fprintf(f, "jurisdiction: %s\n",   buf->meta.jurisdiction[0]   ? buf->meta.jurisdiction   : "International");
    fprintf(f, "max_signatures: %d\n", buf->meta.max_signatures > 0 ? buf->meta.max_signatures : 1);
    fprintf(f, "timestamp: %lld\n",    (long long)time(NULL));
    if (buf->meta.emitter_pubkey[0])   fprintf(f, "public_key: %s\n",           buf->meta.emitter_pubkey);
    if (buf->meta.emitter_sig[0])      fprintf(f, "signature_layer_2: %s\n",    buf->meta.emitter_sig);
    if (buf->meta.receiver_pubkey[0])  fprintf(f, "receiver_public_key: %s\n",  buf->meta.receiver_pubkey);
    if (buf->meta.receiver_sig[0])     fprintf(f, "receiver_signature: %s\n",   buf->meta.receiver_sig);
    if (buf->meta.current_hash[0])     fprintf(f, "current_hash: %s\n",         buf->meta.current_hash);
    if (buf->meta.property_bundle_hash[0]) {
        fprintf(f, "property_bundle_hash: \"%s\"\n", buf->meta.property_bundle_hash);
        fprintf(f, "property_bundle_size: %llu\n", (unsigned long long)buf->meta.property_bundle_size);
        fprintf(f, "property_bundle_destroyed: %s\n", buf->meta.property_bundle_destroyed ? "true" : "false");
    }
    if (buf->bundle_data && buf->bundle_data_len > 0) {
        fprintf(f, "property_bundle: |\n");
        const char* bd = buf->bundle_data;
        size_t remaining = buf->bundle_data_len;
        while (remaining > 0) {
            size_t chunk = remaining < 76 ? remaining : 76;
            fprintf(f, "  %.*s\n", (int)chunk, bd);
            bd += chunk;
            remaining -= chunk;
        }
    }
    fprintf(f, "---\n\n");

    for (int i = 0; i < buf->count; i++) {
        fprintf(f, "%s\n", buf->lines[i]);
    }

    fclose(f);
    strncpy(buf->filename, path, sizeof(buf->filename) - 1);
    buf->modified = 0;
    printf("  [+] Saved: %s\n", path);
    return 0;
}

static int redact_load_bmd(redact_buf_t* buf, const char* path) {
    char clean[1024];
    resolve_bmd_path(path, clean, sizeof(clean));

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean, &doc);
    if (st != BMD_OK) {
        printf("  [-] Cannot load '%s': %s\n", clean, bmd_status_string(st));
        return 1;
    }

    strncpy(buf->meta.block_id,        doc->header.block_id,            sizeof(buf->meta.block_id) - 1);
    strncpy(buf->meta.document_type,   doc->header.document_type,       sizeof(buf->meta.document_type) - 1);
    strncpy(buf->meta.jurisdiction,    doc->header.jurisdiction,         sizeof(buf->meta.jurisdiction) - 1);
    buf->meta.max_signatures = doc->header.max_signatures;
    strncpy(buf->meta.emitter_pubkey,  doc->header.public_key,          sizeof(buf->meta.emitter_pubkey) - 1);
    strncpy(buf->meta.emitter_sig,     doc->header.signature_layer_2,   sizeof(buf->meta.emitter_sig) - 1);
    strncpy(buf->meta.receiver_pubkey, doc->header.receiver_public_key,  sizeof(buf->meta.receiver_pubkey) - 1);
    strncpy(buf->meta.receiver_sig,    doc->header.receiver_signature,   sizeof(buf->meta.receiver_sig) - 1);
    strncpy(buf->meta.current_hash,    doc->header.current_hash,         sizeof(buf->meta.current_hash) - 1);
    strncpy(buf->meta.property_bundle_hash, doc->header.property_bundle_hash, sizeof(buf->meta.property_bundle_hash) - 1);
    buf->meta.property_bundle_size = doc->header.property_bundle_size;
    buf->meta.property_bundle_destroyed = doc->header.property_bundle_destroyed;
    if (buf->bundle_data) {
        free(buf->bundle_data);
        buf->bundle_data = NULL;
        buf->bundle_data_len = 0;
    }
    if (doc->property_bundle_data && doc->property_bundle_data_len > 0) {
        buf->bundle_data = (char*)malloc(doc->property_bundle_data_len + 1);
        if (buf->bundle_data) {
            memcpy(buf->bundle_data, doc->property_bundle_data, doc->property_bundle_data_len);
            buf->bundle_data[doc->property_bundle_data_len] = '\0';
            buf->bundle_data_len = doc->property_bundle_data_len;
        }
    }
    buf->meta.mode_transfer = (doc->header.mode == BMD_MODE_TRANSFER);
    buf->compiled           = buf->meta.mode_transfer;
    buf->count = 0;

    if (doc->payload) {
        const char* p = doc->payload;
        while (*p != '\0' && buf->count < REDACT_MAX_LINES) {
            const char* start = p;
            while (*p != '\0' && *p != '\n') p++;
            size_t len = (size_t)(p - start);
            if (*p == '\n') p++;
            if (len >= REDACT_LINE_CAP) len = REDACT_LINE_CAP - 1;
            memcpy(buf->lines[buf->count], start, len);
            buf->lines[buf->count][len] = '\0';
            buf->count++;
        }
    }

    strncpy(buf->filename, clean, sizeof(buf->filename) - 1);
    buf->modified = 0;
    bmd_document_free(doc);
    return 0;
}

static int cmd_redact_terminal(const char* filepath) {
    enable_ansi_terminal();

    redact_buf_t* buf = (redact_buf_t*)calloc(1, sizeof(redact_buf_t));
    if (!buf) {
        fprintf(stderr, "[-] Out of memory.\n");
        return 1;
    }
    buf->meta.max_signatures = 1;

    /* Load existing file if provided, or set filename for new document */
    if (filepath && filepath[0] != '\0') {
        char clean_fp[1024];
        resolve_bmd_path(filepath, clean_fp, sizeof(clean_fp));
        FILE* ft = fopen(clean_fp, "rb");
        if (ft) {
            fclose(ft);
            if (redact_load_bmd(buf, clean_fp) != 0) {
                free(buf);
                return 1;
            }
        } else {
            /* File does not exist yet: start new document with this filename */
            strncpy(buf->filename, clean_fp, sizeof(buf->filename) - 1);
            buf->modified = 1;
        }
    }

    /* Show manual on first open of blank document */
    if (buf->count == 0 && buf->filename[0] == '\0') {
        redact_clear_screen();
        printf("%s", REDACT_MANUAL);
        printf("  Press ENTER to open the editor.\n  redact-help> ");
        fflush(stdout);
        char tmp[8];
        fgets(tmp, sizeof(tmp), stdin);
    }

    int scroll_top = 0;
    char input[2048];

    while (1) {
        redact_draw(buf, scroll_top);
        printf("  redact> ");
        fflush(stdout);

        if (!fgets(input, sizeof(input), stdin)) break;
        trim_line(input);
        if (input[0] == '\0') continue;

        /* QUIT */
        if (strcmp(input, ":quit") == 0 || strcmp(input, ":q") == 0 || strcmp(input, ":exit") == 0) {
            if (buf->modified) {
                printf("  [!] Unsaved changes. Save with :save, or force-quit with :quit!\n");
                printf("  redact> ");
                fflush(stdout);
                char conf[32];
                fgets(conf, sizeof(conf), stdin);
                trim_line(conf);
                if (strcmp(conf, ":quit!") != 0 && strcmp(conf, ":q!") != 0) continue;
            }
            break;
        }
        if (strcmp(input, ":quit!") == 0 || strcmp(input, ":q!") == 0) break;

        /* HELP */
        if (strcmp(input, ":help") == 0 || strcmp(input, ":h") == 0) {
            redact_clear_screen();
            printf("%s", REDACT_MANUAL);
            printf("  Press ENTER to return.\n  redact-help> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* PREVIEW */
        if (strcmp(input, ":preview") == 0 || strcmp(input, ":p") == 0) {
            redact_show_preview(buf);
            continue;
        }

        /* LIST */
        if (strcmp(input, ":list") == 0 || strcmp(input, ":l") == 0) {
            redact_clear_screen();
            printf("\n  Full line listing (%d lines):\n", buf->count);
            printf("  +--------+--------------------------------------------------------------------+\n");
            for (int i = 0; i < buf->count; i++) {
                printf("  | %6d | %-68.68s |\n", i + 1, buf->lines[i]);
            }
            printf("  +--------+--------------------------------------------------------------------+\n");
            printf("\n  Press ENTER to return.\n  redact-list> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* SCROLL */
        if (strcmp(input, ":down") == 0 || strcmp(input, ":d") == 0) {
            if (scroll_top + 18 < buf->count) scroll_top += 9;
            continue;
        }
        if (strcmp(input, ":up") == 0 || strcmp(input, ":u") == 0) {
            scroll_top -= 9;
            if (scroll_top < 0) scroll_top = 0;
            continue;
        }
        if (strcmp(input, ":top") == 0)    { scroll_top = 0; continue; }
        if (strcmp(input, ":bottom") == 0 || strcmp(input, ":bot") == 0) {
            scroll_top = buf->count > 18 ? buf->count - 18 : 0;
            continue;
        }

        /* SAVE */
        if (strncmp(input, ":save", 5) == 0) {
            const char* arg = input + 5;
            while (*arg == ' ') arg++;
            redact_save_bmd(buf, arg[0] ? arg : NULL);
            printf("  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* SET */
        if (strncmp(input, ":set ", 5) == 0) {
            if (buf->compiled) {
                printf("  [-] Document is sealed (transfer mode). Frontmatter cannot be modified.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            char field[64] = {0};
            const char* rest = input + 5;
            while (*rest == ' ') rest++;
            const char* sp = rest;
            while (*sp && *sp != ' ') sp++;
            size_t flen = (size_t)(sp - rest);
            if (flen >= sizeof(field)) flen = sizeof(field) - 1;
            memcpy(field, rest, flen);
            field[flen] = '\0';
            while (*sp == ' ') sp++;

            if (strcmp(field, "block_id") == 0) {
                strncpy(buf->meta.block_id, sp, sizeof(buf->meta.block_id) - 1);
                buf->modified = 1;
            } else if (strcmp(field, "type") == 0) {
                strncpy(buf->meta.document_type, sp, sizeof(buf->meta.document_type) - 1);
                buf->modified = 1;
            } else if (strcmp(field, "jurisdiction") == 0) {
                strncpy(buf->meta.jurisdiction, sp, sizeof(buf->meta.jurisdiction) - 1);
                buf->modified = 1;
            } else if (strcmp(field, "max_signatures") == 0) {
                int v = atoi(sp);
                buf->meta.max_signatures = (v < 1) ? 1 : (v > 2) ? 2 : v;
                buf->modified = 1;
            } else {
                printf("  [-] Unknown field '%s'.\n", field);
                printf("      Valid fields: block_id  type  jurisdiction  max_signatures\n");
            }
            continue;
        }

        /* ADD */
        if (strncmp(input, ":add ", 5) == 0) {
            if (buf->compiled) {
                printf("  [-] Document is sealed. Content cannot be modified.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->count >= REDACT_MAX_LINES) {
                printf("  [-] Line limit reached (%d lines maximum).\n", REDACT_MAX_LINES);
                continue;
            }
            const char* content = input + 5;
            while (*content == ' ') content++;
            if (strcmp(content, "sign_button") == 0) {
                strncpy(buf->lines[buf->count], "<bmd:sign_button>", REDACT_LINE_CAP - 1);
            } else if (strcmp(content, "cosign_button") == 0) {
                strncpy(buf->lines[buf->count], "<bmd:cosign_button>", REDACT_LINE_CAP - 1);
                buf->meta.max_signatures = 2;
            } else if (strcmp(content, "extract_button") == 0) {
                strncpy(buf->lines[buf->count], "<bmd:extract_button>", REDACT_LINE_CAP - 1);
            } else {
                strncpy(buf->lines[buf->count], content, REDACT_LINE_CAP - 1);
            }
            buf->lines[buf->count][REDACT_LINE_CAP - 1] = '\0';
            buf->count++;
            buf->modified = 1;
            if (buf->count > 18) scroll_top = buf->count - 18;
            continue;
        }

        /* INSERT */
        if (strncmp(input, ":insert ", 8) == 0) {
            if (buf->compiled) {
                printf("  [-] Sealed. Cannot edit.\n"); continue;
            }
            const char* rest = input + 8;
            int n = atoi(rest);
            while (*rest && *rest != ' ') rest++;
            while (*rest == ' ') rest++;
            if (n < 1 || n > buf->count + 1) {
                printf("  [-] Line number out of range (1 to %d).\n", buf->count + 1); continue;
            }
            if (buf->count >= REDACT_MAX_LINES) {
                printf("  [-] Line limit reached.\n"); continue;
            }
            int idx = n - 1;
            for (int i = buf->count; i > idx; i--) {
                memcpy(buf->lines[i], buf->lines[i-1], REDACT_LINE_CAP);
            }
            if (strcmp(rest, "sign_button") == 0) {
                strncpy(buf->lines[idx], "<bmd:sign_button>", REDACT_LINE_CAP - 1);
            } else if (strcmp(rest, "cosign_button") == 0) {
                strncpy(buf->lines[idx], "<bmd:cosign_button>", REDACT_LINE_CAP - 1);
                buf->meta.max_signatures = 2;
            } else if (strcmp(rest, "extract_button") == 0) {
                strncpy(buf->lines[idx], "<bmd:extract_button>", REDACT_LINE_CAP - 1);
            } else {
                strncpy(buf->lines[idx], rest, REDACT_LINE_CAP - 1);
            }
            buf->lines[idx][REDACT_LINE_CAP - 1] = '\0';
            buf->count++;
            buf->modified = 1;
            continue;
        }

        /* DELETE */
        if (strncmp(input, ":delete", 7) == 0) {
            if (buf->compiled) {
                printf("  [-] Sealed. Cannot edit.\n"); continue;
            }
            const char* rest = input + 7;
            while (*rest == ' ') rest++;
            int n = atoi(rest);
            if (n < 1 || n > buf->count) {
                printf("  [-] Line %d does not exist (range: 1 to %d).\n", n, buf->count); continue;
            }
            for (int i = n - 1; i < buf->count - 1; i++) {
                memcpy(buf->lines[i], buf->lines[i+1], REDACT_LINE_CAP);
            }
            buf->count--;
            buf->modified = 1;
            if (scroll_top > 0 && scroll_top >= buf->count)
                scroll_top = buf->count > 0 ? buf->count - 1 : 0;
            continue;
        }

        /* VERIFY */
        if (strcmp(input, ":verify") == 0) {
            if (buf->filename[0] == '\0') {
                printf("  [-] Save the file first with :save <filename.bmd>\n");
            } else {
                cmd_verify(buf->filename);
            }
            printf("  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* INSPECT */
        if (strcmp(input, ":inspect") == 0) {
            if (buf->filename[0] == '\0') {
                printf("  [-] Save the file first with :save <filename.bmd>\n");
            } else {
                cmd_inspect(buf->filename);
            }
            printf("  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* RENDER */
        if (strncmp(input, ":render", 7) == 0) {
            if (buf->filename[0] == '\0') {
                printf("  [-] Save the file first with :save <filename.bmd>\n");
            } else {
                const char* arg = input + 7;
                while (*arg == ' ') arg++;
                cmd_render_forward(buf->filename, arg[0] ? arg : NULL);
            }
            printf("  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* INJECT IP PROPERTY BUNDLE */
        if (strncmp(input, ":inject", 7) == 0 && (input[7] == ' ' || input[7] == '\0' || input[7] == '_' || input[7] == '-')) {
            if (buf->compiled) {
                printf("  [-] Document is already sealed in TRANSFER mode. Cannot inject property.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            char dir_buf[1024] = {0};
            const char* dir = input + 7;
            if (*dir == '_' || *dir == '-') {
                while (*dir && *dir != ' ') dir++;
            }
            while (*dir == ' ') dir++;
            if (*dir == '\0') {
                printf("  [?] Enter path to directory or file to inject (e.g. ./my_code): ");
                fflush(stdout);
                if (!fgets(dir_buf, sizeof(dir_buf), stdin)) continue;
                trim_line(dir_buf);
                if (dir_buf[0] == '\0') {
                    printf("  Cancelled.\n");
                    continue;
                }
                dir = dir_buf;
            }

            char clean_dir[1024];
            strncpy(clean_dir, dir, sizeof(clean_dir) - 1);
            clean_dir[sizeof(clean_dir) - 1] = '\0';
            sanitize_path(clean_dir);

            FILE* test_f = fopen(clean_dir, "rb");
            DWORD attr = GetFileAttributesA(clean_dir);
            if (!test_f && attr == (DWORD)-1) {
                printf("  [-] Path not found on laptop: '%s'\n", clean_dir);
                printf("      Please verify that the file or directory exists.\n");
                printf("  Press ENTER to continue.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (test_f) fclose(test_f);

            if (buf->filename[0] == '\0') {
                printf("  [?] No document filename set. Enter filename to save as (e.g. contract.bmd): ");
                fflush(stdout);
                char fname_input[1024];
                if (!fgets(fname_input, sizeof(fname_input), stdin)) continue;
                trim_line(fname_input);
                if (fname_input[0] == '\0') {
                    printf("  Cancelled.\n");
                    continue;
                }
                sanitize_path(fname_input);
                if (strlen(fname_input) < 4 || strcmp(fname_input + strlen(fname_input) - 4, ".bmd") != 0) {
                    snprintf(buf->filename, sizeof(buf->filename), "%s.bmd", fname_input);
                } else {
                    strncpy(buf->filename, fname_input, sizeof(buf->filename) - 1);
                }
            }

            printf("\n  [+] Saving current document before injection...\n");
            if (redact_save_bmd(buf, NULL) != 0) continue;

            printf("  [+] Injecting and encrypting property from: %s\n", clean_dir);
            int rc = cmd_inject_property_forward(clean_dir, buf->filename);
            if (rc == 0) {
                redact_load_bmd(buf, buf->filename);
                buf->modified = 1;

                /* Auto-append <bmd:extract_button> if not present in lines */
                bool has_btn = false;
                for (int i = 0; i < buf->count; i++) {
                    if (strstr(buf->lines[i], "extract_button")) { has_btn = true; break; }
                }
                if (!has_btn && buf->count < REDACT_MAX_LINES) {
                    strncpy(buf->lines[buf->count++], "<bmd:extract_button>", REDACT_LINE_CAP - 1);
                    redact_save_bmd(buf, NULL);
                    printf("  [+] Appended <bmd:extract_button> to document layout.\n");
                }

                printf("\n  ================================================================\n");
                printf("  [+] IP PROPERTY INJECTED & SECURELY SEALED INTO BLOCK!\n");
                printf("  ================================================================\n");
                printf("  Source files were moved/destroyed on disk (True Ownership Transfer).\n");
                printf("  The bundle is compressed and encrypted with ChaCha20.\n");
            } else {
                printf("\n  [-] Injection failed. Ensure the directory exists.\n");
            }
            printf("\n  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* EXTRACT IP PROPERTY BUNDLE */
        if (strncmp(input, ":extract", 8) == 0 && (input[8] == ' ' || input[8] == '\0' || input[8] == '_' || input[8] == '-')) {
            if (buf->filename[0] == '\0') {
                printf("  [-] No document loaded.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->meta.property_bundle_hash[0] == '\0' && !buf->bundle_data) {
                printf("  [-] No IP Property Bundle found in this document.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            const char* out_arg = input + 8;
            if (*out_arg == '_' || *out_arg == '-') {
                while (*out_arg && *out_arg != ' ') out_arg++;
            }
            while (*out_arg == ' ') out_arg++;

            char clean_out[1024] = {0};
            if (out_arg[0] != '\0') {
                strncpy(clean_out, out_arg, sizeof(clean_out) - 1);
                sanitize_path(clean_out);
            } else {
                strncpy(clean_out, "./extracted_ip", sizeof(clean_out) - 1);
            }
            char abs_out[1024] = {0};
#if defined(_WIN32)
            if (!_fullpath(abs_out, clean_out, sizeof(abs_out) - 1)) {
                strncpy(abs_out, clean_out, sizeof(abs_out) - 1);
            }
#else
            if (!realpath(clean_out, abs_out)) {
                strncpy(abs_out, clean_out, sizeof(abs_out) - 1);
            }
#endif
            printf("\n  [+] Extracting and decrypting IP bundle to: %s\n", abs_out);
            int rc = cmd_extract_property_forward(buf->filename, clean_out);
            if (rc == 0) {
                printf("\n  ================================================================\n");
                printf("  [+] EXTRACTION SUCCESSFUL!\n");
                printf("  ================================================================\n");
                printf("  Your files have been decrypted and restored to this folder:\n");
                printf("  -> %s\n", abs_out);
                printf("  ================================================================\n");
            } else {
                printf("  [-] Extraction failed.\n");
            }
            printf("\n  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* SIGN (Signs as Emitter in DRAFT mode; does NOT freeze document!) */
        if (strncmp(input, ":sign", 5) == 0 && (input[5] == ' ' || input[5] == '\0')) {
            if (buf->compiled) {
                printf("  [-] Document is already sealed in TRANSFER mode and cannot be modified.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->filename[0] == '\0') {
                printf("  [?] No filename set. Enter filename to save as (e.g. contract.bmd): ");
                fflush(stdout);
                char fname_input[1024];
                if (!fgets(fname_input, sizeof(fname_input), stdin)) continue;
                trim_line(fname_input);
                if (fname_input[0] == '\0') {
                    printf("  Cancelled.\n");
                    continue;
                }
                strncpy(buf->filename, fname_input, sizeof(buf->filename) - 1);
                buf->filename[sizeof(buf->filename) - 1] = '\0';
            }

            printf("\n  [+] Saving draft...\n");
            if (redact_save_bmd(buf, NULL) != 0) continue;

            int rc = cmd_sign(buf->filename, NULL);
            if (rc == 0) {
                redact_load_bmd(buf, buf->filename);
                buf->compiled = 0; /* Remains in DRAFT mode! */
                printf("\n  [+] Document signed as Emitter! Document remains in DRAFT (mutable) mode.\n");
                printf("      You may continue adding lines/buttons. When ready to seal forever, run :compile.\n");
            } else {
                printf("  [-] Sign failed.\n");
            }
            printf("\n  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* COMPILE — Freezes document to immutable TRANSFER mode with retro purple loading bar */
        if (strcmp(input, ":compile") == 0 || strncmp(input, ":compile ", 9) == 0) {
            if (buf->compiled) {
                printf("  [-] Document is already compiled and sealed in TRANSFER mode.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->count == 0) {
                printf("  [-] Document has no content. Add lines with :add before compiling.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->filename[0] == '\0') {
                printf("  [?] No filename set. Enter filename to save as (e.g. contract.bmd): ");
                fflush(stdout);
                char fname_input[1024];
                if (!fgets(fname_input, sizeof(fname_input), stdin)) continue;
                trim_line(fname_input);
                if (fname_input[0] == '\0') {
                    printf("  Cancelled.\n");
                    continue;
                }
                strncpy(buf->filename, fname_input, sizeof(buf->filename) - 1);
                buf->filename[sizeof(buf->filename) - 1] = '\0';
            }

            printf("\n  [+] Saving draft to disk...\n");
            if (redact_save_bmd(buf, NULL) != 0) continue;

            int rc = cmd_compile(buf->filename, NULL);
            if (rc == 0) {
                redact_load_bmd(buf, buf->filename);
                buf->compiled = 1;

                /* Resolve absolute path of the compiled file */
                char abs_path[1024] = {0};
#if defined(_WIN32)
                if (!_fullpath(abs_path, buf->filename, sizeof(abs_path) - 1)) {
                    strncpy(abs_path, buf->filename, sizeof(abs_path) - 1);
                }
#else
                if (!realpath(buf->filename, abs_path)) {
                    strncpy(abs_path, buf->filename, sizeof(abs_path) - 1);
                }
#endif
                printf("\n  ================================================================\n");
                printf("  [+] COMPILE SUCCESSFUL — DOCUMENT SEALED (TRANSFER MODE)\n");
                printf("  ================================================================\n");
                printf("  File         : %s\n", abs_path);
                printf("  SHA-512 Hash : %.64s\n", buf->meta.current_hash);
                printf("               : %.64s\n", buf->meta.current_hash + 64);
                printf("  Pubkey       : %.64s\n", buf->meta.emitter_pubkey);
                printf("  Signature    : %.64s...\n", buf->meta.emitter_sig);
                printf("  Mode         : TRANSFER (IMMUTABLE SEALED)\n");
                printf("  Disk Status  : Read-only locked (tamper-proof)\n");
                printf("  ================================================================\n");
                if (buf->meta.max_signatures >= 2) {
                    printf("\n  Next step: Receiver must co-sign to ratify.\n");
                    printf("  Receiver runs:  :cosign\n");
                }
            } else {
                printf("  [-] Compile failed.\n");
            }
            printf("\n  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp2[8]; fgets(tmp2, sizeof(tmp2), stdin);
            continue;
        }

        /* COSIGN */
        if (strncmp(input, ":cosign", 7) == 0 && (input[7] == ' ' || input[7] == '\0')) {
            if (!buf->meta.emitter_sig[0]) {
                printf("  [-] Document must be signed by Emitter first:  :sign\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->meta.max_signatures < 2) {
                printf("  [-] Co-sign is not permitted.\n");
                printf("      max_signatures = %d (unilateral). This document is sealed by Emitter only.\n",
                       buf->meta.max_signatures);
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->meta.receiver_sig[0]) {
                printf("  [-] Document is already co-signed. Signature cap reached.\n");
                printf("  Press ENTER.\n  redact> ");
                fflush(stdout);
                char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
                continue;
            }
            if (buf->filename[0] == '\0') {
                printf("  [?] No filename set. Enter filename to save as (e.g. contract.bmd): ");
                fflush(stdout);
                char fname_input[1024];
                if (!fgets(fname_input, sizeof(fname_input), stdin)) continue;
                trim_line(fname_input);
                if (fname_input[0] == '\0') {
                    printf("  Cancelled.\n");
                    continue;
                }
                strncpy(buf->filename, fname_input, sizeof(buf->filename) - 1);
                buf->filename[sizeof(buf->filename) - 1] = '\0';
                if (redact_save_bmd(buf, NULL) != 0) continue;
            }
            int rc = cmd_cosign(buf->filename, NULL);
            if (rc == 0) {
                redact_load_bmd(buf, buf->filename);
                printf("  [+] Co-signed successfully with authentic Receiver key!\n");
                printf("      Document is now CONSENSUS RATIFIED (dual-signed).\n");
            } else {
                printf("  [-] Co-sign failed.\n");
            }
            printf("  Press ENTER to continue.\n  redact> ");
            fflush(stdout);
            char tmp[8]; fgets(tmp, sizeof(tmp), stdin);
            continue;
        }

        /* OPEN / READ another file */
        if (strncmp(input, ":read ", 6) == 0 || strncmp(input, ":open ", 6) == 0) {
            if (buf->modified) {
                printf("  [!] Unsaved changes. Save first with :save, then try again.\n"); continue;
            }
            const char* arg = input + 6;
            while (*arg == ' ') arg++;
            memset(buf, 0, sizeof(redact_buf_t));
            buf->meta.max_signatures = 1;
            redact_load_bmd(buf, arg);
            scroll_top = 0;
            continue;
        }

        /* Unknown command */
        printf("  [-] Unknown command: '%s'\n", input);
        printf("      Type :help to see the full manual and command list.\n");
        printf("  Press ENTER to continue.\n  redact> ");
        fflush(stdout);
        char tmp_unk[8]; fgets(tmp_unk, sizeof(tmp_unk), stdin);
    }

    printf("\n  [*] Redact Studio closed.\n\n");
    if (buf->bundle_data) free(buf->bundle_data);
    free(buf);
    return 0;
}

static int cmd_export_office(const char* filepath) {
    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        printf("{\"status\":\"error\",\"error\":\"%s\"}\n", bmd_status_string(st));
        return 1;
    }

    st = bmd_verify_document(doc);
    bool valid = (st == BMD_OK);

    printf("{\n");
    printf("  \"status\": \"%s\",\n", valid ? "verified" : "unverified");
    printf("  \"block_id\": \"%s\",\n", doc->header.block_id);
    printf("  \"document_type\": \"%s\",\n", doc->header.document_type);
    printf("  \"mode\": \"%s\",\n", bmd_mode_string(doc->header.mode));
    printf("  \"current_hash\": \"%s\",\n", doc->header.current_hash);
    printf("  \"emitter_pubkey\": \"%s\",\n", doc->header.public_key);
    printf("  \"emitter_signature\": \"%s\",\n", doc->header.signature_layer_2);
    printf("  \"receiver_pubkey\": \"%s\",\n", doc->header.receiver_public_key);
    printf("  \"receiver_signature\": \"%s\",\n", doc->header.receiver_signature);
    printf("  \"dual_signed\": %s,\n", (doc->header.receiver_signature[0] != '\0') ? "true" : "false");
    printf("  \"timestamp\": %lld,\n", (long long)doc->header.timestamp);
    printf("  \"payload_length\": %zu\n", doc->payload ? strlen(doc->payload) : 0);
    printf("}\n");

    bmd_document_free(doc);
    return valid ? 0 : 2;
}

/* ---- Terminal typography helpers (legal document hierarchy) ---- */

/* Centre a plain text string inside the 76-char letter-sheet column.
   The printable width of the sheet interior is 76 chars (between "  |" borders).
   We pad the text to fill that width so the right border aligns. */
static void print_sheet_centered(const char* text) {
    int len = (int)strlen(text);
    int interior = 76;   /* chars between the two "  |" borders */
    int pad_total = interior - len;
    if (pad_total < 0) pad_total = 0;
    int pad_left  = pad_total / 2;
    int pad_right = pad_total - pad_left;
    /* Build padded string manually to avoid dynamic alloc */
    char buf[256];
    int bi = 0;
    for (int i = 0; i < pad_left  && bi < 254; i++) buf[bi++] = ' ';
    for (int i = 0; text[i] && bi < 254; i++)        buf[bi++] = text[i];
    for (int i = 0; i < pad_right && bi < 254; i++)  buf[bi++] = ' ';
    buf[bi] = '\0';
    printf("  |%s|\n", buf);
}

/* TITLE — bold white, centred, uppercased, with surrounding blank lines.
   Professional legal ratio: title is visually dominant (2× body weight). */
static void print_sheet_title(const char* text) {
    /* Convert to uppercase */
    char upper[256];
    int i;
    for (i = 0; text[i] && i < 253; i++)
        upper[i] = (char)(((unsigned char)text[i] >= 'a' && (unsigned char)text[i] <= 'z')
                          ? text[i] - 32 : text[i]);
    upper[i] = '\0';

    /* Compose: *** TITLE *** */
    char decorated[256];
    snprintf(decorated, sizeof(decorated), "*** %s ***", upper);

    /* Centre inside 76-char interior */
    int len  = (int)strlen(decorated);
    int interior = 76;
    int pad_total = interior - len;
    if (pad_total < 0) pad_total = 0;
    int pad_left  = pad_total / 2;
    int pad_right = pad_total - pad_left;
    char lpad[128] = {0}, rpad[128] = {0};
    memset(lpad, ' ', (size_t)pad_left);
    memset(rpad, ' ', (size_t)pad_right);

    printf("  |                                                                            |\n");
    /* ANSI bold bright-white for title prominence */
    printf("  |\033[1;97m%s%s%s\033[0m|\n", lpad, decorated, rpad);
    printf("  |                                                                            |\n");
}

/* SUBTITLE — centred, muted (dim), delimited with dashes */
static void print_sheet_subtitle(const char* text) {
    char decorated[256];
    snprintf(decorated, sizeof(decorated), "-- %s --", text);
    /* ANSI dim/italic for subtitle (subordinate to title) */
    int len  = (int)strlen(decorated);
    int interior = 76;
    int pad_total = interior - len;
    if (pad_total < 0) pad_total = 0;
    int pad_left  = pad_total / 2;
    int pad_right = pad_total - pad_left;
    char lpad[128] = {0}, rpad[128] = {0};
    memset(lpad, ' ', (size_t)pad_left);
    memset(rpad, ' ', (size_t)pad_right);
    printf("  |\033[2m%s%s%s\033[0m|\n", lpad, decorated, rpad);
    printf("  |                                                                            |\n");
}

/* HEADING — uppercase section header with === delimiters, bold */
static void print_sheet_heading(const char* text) {
    char upper[256];
    int i;
    for (i = 0; text[i] && i < 253; i++)
        upper[i] = (char)(((unsigned char)text[i] >= 'a' && (unsigned char)text[i] <= 'z')
                          ? text[i] - 32 : text[i]);
    upper[i] = '\0';

    char decorated[256];
    snprintf(decorated, sizeof(decorated), "=== %s ===", upper);

    int len  = (int)strlen(decorated);
    int interior = 76;
    int pad_total = interior - len;
    if (pad_total < 0) pad_total = 0;
    int pad_left  = pad_total / 2;
    int pad_right = pad_total - pad_left;
    char lpad[128] = {0}, rpad[128] = {0};
    memset(lpad, ' ', (size_t)pad_left);
    memset(rpad, ' ', (size_t)pad_right);
    printf("  |                                                                            |\n");
    printf("  |\033[1m%s%s%s\033[0m|\n", lpad, decorated, rpad);
}

/* BODY — left-aligned, word-wrapped at 72 cols (standard legal body text) */
static void print_sheet_line(const char* text) {
    if (!text || *text == '\0') {
        printf("  |                                                                            |\n");
        return;
    }
    const char* p = text;
    while (*p != '\0') {
        while (*p == ' ') p++;
        if (*p == '\0') break;

        size_t len = strlen(p);
        if (len <= 72) {
            printf("  |  %-72.72s  |\n", p);
            break;
        }

        size_t break_idx = 72;
        while (break_idx > 40 && p[break_idx] != ' ') {
            break_idx--;
        }
        if (p[break_idx] != ' ') break_idx = 72;

        char buf[80];
        memcpy(buf, p, break_idx);
        buf[break_idx] = '\0';
        printf("  |  %-72.72s  |\n", buf);

        p += break_idx;
        while (*p == ' ') p++;
    }
}

static int cmd_view(const char* filepath) {
    enable_ansi_terminal();

    char clean_path[1024];
    resolve_bmd_path(filepath, clean_path, sizeof(clean_path));

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_file(clean_path, &doc);
    if (st != BMD_OK) {
        fprintf(stderr, "[-] Error loading file '%s': %s\n", clean_path, bmd_status_string(st));
        return 1;
    }

    bmd_status_t v_st = bmd_verify_document(doc);
    bool valid = (v_st == BMD_OK);
    bool dual_signed = (doc->header.receiver_signature[0] != '\0');

    printf("\n");
    printf("  +----------------------------------------------------------------------------+\n");
    printf("  |                                                                            |\n");
    if (valid && dual_signed) {
        printf("  |  [VALID] BLOCKCHAIN MARKDOWN IMMUTABLE DOCUMENT - CONSENSUS RATIFIED       |\n");
    } else if (valid) {
        printf("  |  [VALID] BLOCKCHAIN MARKDOWN IMMUTABLE DOCUMENT - CRYPTOGRAPHICALLY SEALED |\n");
    } else {
        printf("  |  [SECURITY ALERT] CONTINGENCY ALERT: INTEGRITY COMPROMISED / HASH BREACH   |\n");
    }
    printf("  |  ========================================================================  |\n");
    printf("  |                                                                            |\n");
    if (doc->header.block_id[0] != '\0') {
        printf("  |  BLOCK ID      : %-56.56s  |\n", doc->header.block_id);
    }
    printf("  |  DOCUMENT TYPE : %-56.56s  |\n", doc->header.document_type[0] ? doc->header.document_type : "unspecified");
    printf("  |  MODE          : %-56.56s  |\n", doc->header.mode == BMD_MODE_TRANSFER ? "transfer (FROZEN IMMUTABLE)" : "draft (MUTABLE DRAFT)");
    printf("  |  JURISDICTION  : %-56.56s  |\n", doc->header.jurisdiction[0] ? doc->header.jurisdiction : "International");
    if (doc->header.max_signatures > 0) {
        int current_sigs = (doc->header.signature_layer_2[0] != '\0' ? 1 : 0) + (dual_signed ? 1 : 0);
        char cap_buf[64];
        snprintf(cap_buf, sizeof(cap_buf), "%d / %d (%s)", current_sigs, doc->header.max_signatures,
                 current_sigs >= doc->header.max_signatures ? "LIMIT REACHED - RATIFIED" : "OPEN");
        printf("  |  SIGNATURE CAP : %-56.56s  |\n", cap_buf);
    }
    printf("  |  SHA-512 HASH  : %-56.56s  |\n", doc->header.current_hash);
    if (strlen(doc->header.current_hash) > 56) {
        printf("  |  HASH (CONT)   : %-56.56s  |\n", doc->header.current_hash + 56);
    }
    printf("  |                                                                            |\n");
    printf("  |  ------------------------------------------------------------------------  |\n");
    printf("  |                                                                            |\n");

    if (doc->payload) {
        const char* p = doc->payload;
        char line[1024];
        while (*p != '\0') {
            const char* start = p;
            while (*p != '\0' && *p != '\n') p++;
            size_t len = p - start;
            if (*p == '\n') p++;

            if (len >= sizeof(line)) len = sizeof(line) - 1;
            memcpy(line, start, len);
            line[len] = '\0';
            trim_line(line);

            if (line[0] == '\0') {
                print_sheet_line("");
                continue;
            }

            if (strstr(line, "<bmd:sign_button>") || strstr(line, "<!-- bmd:sign_button -->")) {
                if (doc->header.signature_layer_2[0] != '\0') {
                    printf("  |  +-- [ BUTTON: SIGN AS EMITTER ] ----------------------------------------+ |\n");
                    printf("  |  | Status: DIGITALLY SEALED (Ed25519 Verified)                           | |\n");
                    printf("  |  | Pubkey: %-61.61s | |\n", doc->header.public_key);
                    printf("  |  +-----------------------------------------------------------------------+ |\n");
                } else {
                    printf("  |  +-- [ BUTTON: SIGN AS EMITTER ] ----------------------------------------+ |\n");
                    printf("  |  | Status: PENDING SIGNATURE (Unsigned draft)                            | |\n");
                    printf("  |  +-----------------------------------------------------------------------+ |\n");
                }
                continue;
            }
            if (strstr(line, "<bmd:cosign_button>") || strstr(line, "<!-- bmd:cosign_button -->")) {
                if (doc->header.receiver_signature[0] != '\0') {
                    printf("  |  +-- [ BUTTON: CO-SIGN AS RECEIVER ] ------------------------------------+ |\n");
                    printf("  |  | Status: CO-SIGNED & RATIFIED (Ed25519 Ratified)                       | |\n");
                    printf("  |  | Pubkey: %-61.61s | |\n", doc->header.receiver_public_key);
                    printf("  |  +-----------------------------------------------------------------------+ |\n");
                } else {
                    printf("  |  +-- [ BUTTON: CO-SIGN AS RECEIVER ] ------------------------------------+ |\n");
                    printf("  |  | Status: AWAITING COUNTERPARTY RATIFICATION                            | |\n");
                    printf("  |  +-----------------------------------------------------------------------+ |\n");
                }
                continue;
            }
            if (strstr(line, "<bmd:extract_button>") || strstr(line, "<!-- bmd:extract_button -->")) {
                if (doc->header.property_bundle_hash[0] != '\0') {
                    printf("  |  +-- [ BUTTON: EXTRACT INTELLIGENT PROPERTY (IP) ] ----------------------+ |\n");
                    printf("  |  | Status: DIGITALLY SEALED (ChaCha20-Poly1305 Encrypted)                | |\n");
                    printf("  |  | Asset : %llu bytes | Extract with: bmd --extract-property             | |\n",
                           (unsigned long long)doc->header.property_bundle_size);
                    printf("  |  +-----------------------------------------------------------------------+ |\n");
                } else {
                    printf("  |  +-- [ BUTTON: EXTRACT INTELLIGENT PROPERTY (IP) ] ----------------------+ |\n");
                    printf("  |  | Status: NO ASSET ATTACHED (Use :inject <path> in Studio)              | |\n");
                    printf("  |  +-----------------------------------------------------------------------+ |\n");
                }
                continue;
            }
            if (strstr(line, "<!-- bmd:rule double -->") || strstr(line, "<bmd:rule double>") || strstr(line, "<bmd:rule>")) {
                printf("  |  ========================================================================  |\n");
                continue;
            }
            if (strstr(line, "<!-- bmd:rule single -->") || strstr(line, "<bmd:rule single>")) {
                printf("  |  ------------------------------------------------------------------------  |\n");
                continue;
            }
            if (strstr(line, "<!-- bmd:parties -->") || strstr(line, "<bmd:parties>")) {
                printf("  |  +-- FIRST PARTY (EMITTER) --------------+-- SECOND PARTY (RECEIVER) ----+ |\n");
                printf("  |  | %-37.37s | %-36.36s | |\n",
                       doc->header.public_key[0] ? doc->header.public_key : "(Pending)",
                       doc->header.receiver_public_key[0] ? doc->header.receiver_public_key : "(Not required / Pending)");
                printf("  |  +---------------------------------------+-------------------------------+ |\n");
                continue;
            }
            if (strstr(line, "<!-- bmd:signatures -->") || strstr(line, "<bmd:signatures>")) {
                printf("  |  +== EMITTER SIGNATURE (Ed25519) ========+== RECEIVER CO-SIGNATURE ======+ |\n");
                printf("  |  | Status: %-29.29s | Status: %-27.27s | |\n",
                       doc->header.signature_layer_2[0] ? "DIGITALLY SEALED" : "PENDING",
                       doc->header.receiver_signature[0] ? "CO-SIGNED & RATIFIED" : (doc->header.max_signatures == 2 ? "AWAITING RATIFICATION" : "UNILATERAL / N/A"));
                printf("  |  | Sig: %-32.32s... | Sig: %-30.30s... | |\n",
                       doc->header.signature_layer_2,
                       doc->header.receiver_signature[0] ? doc->header.receiver_signature : "--");
                printf("  |  +=======================================+===============================+ |\n");
                continue;
            }
            if (strstr(line, "<!-- bmd:seal -->") || strstr(line, "<bmd:seal>")) {
                printf("  |  [*] BLOCKCHAIN MARKDOWN CRYPTOGRAPHIC CUSTODY SEAL: SHA-512 VERIFIED [*] |\n");
                continue;
            }
            if (strncmp(line, "<!-- bmd:", 9) == 0) continue;

            /* Parse typography tags: <title>, <subtitle>, <heading>, <body> */
            char clean_text[1024];
            if (strstr(line, "<title>")) {
                char* s1 = strstr(line, "<title>") + 7;
                char* s2 = strstr(s1, "</title>");
                size_t tlen = s2 ? (size_t)(s2 - s1) : strlen(s1);
                if (tlen >= sizeof(clean_text)) tlen = sizeof(clean_text) - 1;
                memcpy(clean_text, s1, tlen);
                clean_text[tlen] = '\0';
                print_sheet_title(clean_text);
            } else if (strstr(line, "<subtitle>")) {
                char* s1 = strstr(line, "<subtitle>") + 10;
                char* s2 = strstr(s1, "</subtitle>");
                size_t tlen = s2 ? (size_t)(s2 - s1) : strlen(s1);
                if (tlen >= sizeof(clean_text)) tlen = sizeof(clean_text) - 1;
                memcpy(clean_text, s1, tlen);
                clean_text[tlen] = '\0';
                print_sheet_subtitle(clean_text);
            } else if (strstr(line, "<heading>")) {
                char* s1 = strstr(line, "<heading>") + 9;
                char* s2 = strstr(s1, "</heading>");
                size_t tlen = s2 ? (size_t)(s2 - s1) : strlen(s1);
                if (tlen >= sizeof(clean_text)) tlen = sizeof(clean_text) - 1;
                memcpy(clean_text, s1, tlen);
                clean_text[tlen] = '\0';
                print_sheet_heading(clean_text);
            } else if (strstr(line, "<body>")) {
                char* s1 = strstr(line, "<body>") + 6;
                char* s2 = strstr(s1, "</body>");
                size_t tlen = s2 ? (size_t)(s2 - s1) : strlen(s1);
                if (tlen >= sizeof(clean_text)) tlen = sizeof(clean_text) - 1;
                memcpy(clean_text, s1, tlen);
                clean_text[tlen] = '\0';
                print_sheet_line(clean_text);
            } else if (strncmp(line, "# ", 2) == 0) {
                print_sheet_title(line + 2);
            } else if (strncmp(line, "## ", 3) == 0) {
                print_sheet_subtitle(line + 3);
            } else if (strncmp(line, "### ", 4) == 0) {
                print_sheet_heading(line + 4);
            } else {
                print_sheet_line(line);
            }
        }
    }

    printf("  |                                                                            |\n");
    printf("  +----------------------------------------------------------------------------+\n");
    if (doc->header.block_id[0] != '\0') {
        printf("  [ END OF IMMUTABLE BLOCK RECORD: %s ]\n\n", doc->header.block_id);
    } else {
        printf("  [ END OF IMMUTABLE BLOCK RECORD - SHA-512 VERIFIED ]\n\n");
    }

    bmd_document_free(doc);
    return valid ? 0 : 2;
}

static void run_interactive_shell(void) {
    print_banner();
    printf("  [ Interactive Blockchain Markdown (BMD) Shell ]\n");
    printf("  Type 'read <file.bmd>' to view an immutable document natively.\n");
    printf("  Type '/help' for full command manual, 'exit' or 'quit' to close.\n\n");

    char line_buf[2048];
    while (1) {
        printf("\033[1;38;2;245;75;225mbmd>\033[0m ");
        fflush(stdout);

        if (!fgets(line_buf, sizeof(line_buf), stdin)) {
            break;
        }

        trim_line(line_buf);
        if (line_buf[0] == '\0') continue;

        if (strcmp(line_buf, "exit") == 0 || strcmp(line_buf, "quit") == 0 || strcmp(line_buf, "q") == 0) {
            printf("[*] Shell closed.\n");
            break;
        }

        if (strcmp(line_buf, "help") == 0 || strcmp(line_buf, "/help") == 0 ||
            strcmp(line_buf, "--help") == 0 || strcmp(line_buf, "-h") == 0 ||
            strcmp(line_buf, "?") == 0) {
            print_help();
            continue;
        }

        /* Parse command and arguments */
        char cmd[64] = {0};
        char arg1[1024] = {0};
        char arg2[1024] = {0};

        /* Extract cmd */
        const char* p = line_buf;
        while (*p && *p != ' ' && *p != '\t') p++;
        size_t cmd_len = p - line_buf;
        if (cmd_len >= sizeof(cmd)) cmd_len = sizeof(cmd) - 1;
        memcpy(cmd, line_buf, cmd_len);
        cmd[cmd_len] = '\0';

        while (*p == ' ' || *p == '\t') p++;

        /* Extract arg1, respecting quotes */
        if (*p != '\0') {
            if (*p == '"' || *p == '\'') {
                char q = *p++;
                const char* a_start = p;
                while (*p && *p != q) p++;
                size_t a_len = p - a_start;
                if (a_len >= sizeof(arg1)) a_len = sizeof(arg1) - 1;
                memcpy(arg1, a_start, a_len);
                arg1[a_len] = '\0';
                if (*p == q) p++;
            } else {
                const char* a_start = p;
                while (*p && *p != ' ' && *p != '\t') p++;
                size_t a_len = p - a_start;
                if (a_len >= sizeof(arg1)) a_len = sizeof(arg1) - 1;
                memcpy(arg1, a_start, a_len);
                arg1[a_len] = '\0';
            }
        }

        while (*p == ' ' || *p == '\t') p++;

        /* Extract arg2 */
        if (*p != '\0') {
            strncpy(arg2, p, sizeof(arg2) - 1);
            trim_line(arg2);
        }

        sanitize_path(arg1);

        if (strcmp(cmd, "help") == 0 || strcmp(cmd, "/help") == 0 ||
            strcmp(cmd, "--help") == 0 || strcmp(cmd, "-h") == 0 ||
            strcmp(cmd, "?") == 0) {
            print_help();
        } else if (strcmp(cmd, "read") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: read <file.bmd>\n");
            } else {
                cmd_view(arg1);
            }
        } else if (strcmp(cmd, "verify") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: verify <file.bmd>\n");
            } else {
                cmd_verify(arg1);
            }
        } else if (strcmp(cmd, "inspect") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: inspect <file.bmd>\n");
            } else {
                cmd_inspect(arg1);
            }
        } else if (strcmp(cmd, "sign") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: sign <file.bmd> [seed_hex]\n");
            } else {
                cmd_sign(arg1, arg2[0] ? arg2 : NULL);
            }
        } else if (strcmp(cmd, "compile") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: compile <file.bmd> [seed_hex]\n");
            } else {
                cmd_compile(arg1, arg2[0] ? arg2 : NULL);
            }
        } else if (strcmp(cmd, "cosign") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: cosign <file.bmd> [seed_hex]\n");
            } else {
                cmd_cosign(arg1, arg2[0] ? arg2 : NULL);
                lock_file_readonly(arg1);
            }
        } else if (strcmp(cmd, "lock") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: lock <file.bmd>\n");
            } else {
                lock_file_readonly(arg1);
            }
        } else if (strcmp(cmd, "render") == 0) {
            if (arg1[0] == '\0') {
                printf("[-] Usage: render <file.bmd> [output.html]\n");
            } else {
                cmd_render_forward(arg1, arg2[0] ? arg2 : NULL);
            }
        } else if (strcmp(cmd, "redact") == 0) {
            cmd_redact_terminal(arg1);
        } else {
            /* If the user just typed a file path directly */
            size_t l = strlen(cmd);
            if (l > 4 && strcmp(cmd + l - 4, ".bmd") == 0) {
                sanitize_path(cmd);
                cmd_view(cmd);
            } else {
                printf("[-] Unknown command: '%s'. Type '/help' for available commands.\n", cmd);
            }
        }
    }
}

static int cmd_audit(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "[-] At least one .bmd file is required to audit.\n");
        return 1;
    }

    const char** files = (const char**)&argv[2];
    size_t count = (size_t)(argc - 2);

    bmd_chain_report_t report;
    bmd_status_t st = bmd_verify_chain(files, count, &report);

    printf("\n=== CRYPTOGRAPHIC LEDGER AUDIT REPORT ===\n");
    printf("  Total Blocks Evaluated : %zu\n", report.total_blocks);
    printf("  Valid Blocks           : %zu\n", report.valid_blocks);
    printf("  Corrupted Blocks       : %zu\n", report.corrupted_blocks);
    printf("  Last Valid Hash        : %s\n", report.last_valid_hash);
    printf("  Security Ruling        : %s\n", (st == BMD_OK) ? "POSITIVE CONSENSUS" : "REJECTED DUE TO TAMPER/CHAIN BREACH");
    printf("  Executive Summary      : %s\n\n", report.audit_summary);

    return (st == BMD_OK) ? 0 : 3;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        run_interactive_shell();
        return 0;
    }

    const char* cmd = argv[1];

    /* Help manual dispatch */
    if (strcmp(cmd, "/help") == 0 || strcmp(cmd, "help") == 0 ||
        strcmp(cmd, "--help") == 0 || strcmp(cmd, "-h") == 0 ||
        strcmp(cmd, "/?") == 0 || strcmp(cmd, "?") == 0) {
        print_banner();
        print_help();
        return 0;
    }

    /* Short form: bmd read <file.bmd> */
    if (strcmp(cmd, "read") == 0) {
        if (argc >= 3) {
            return cmd_view(argv[2]);
        } else {
            fprintf(stderr, "[-] Usage: bmd read <file.bmd>\n");
            return 1;
        }
    } else if (strcmp(cmd, "lock") == 0) {
        if (argc >= 3) {
            return lock_file_readonly(argv[2]);
        } else {
            fprintf(stderr, "[-] Usage: bmd lock <file.bmd>\n");
            return 1;
        }
    } else if (argc == 2) {
        /* Direct short form: bmd <file.bmd> */
        size_t l = strlen(cmd);
        if (l > 4 && strcmp(cmd + l - 4, ".bmd") == 0) {
            return cmd_view(cmd);
        }
    }

    if ((strcmp(cmd, "--verify") == 0 && argc >= 3) ||
        (strcmp(cmd, "verify") == 0 && argc >= 4 && strcmp(argv[2], "--json") == 0)) {
        const char* target_file = (strcmp(cmd, "verify") == 0) ? argv[3] : argv[2];
        return cmd_verify_json(target_file);
    } else if (strcmp(cmd, "verify") == 0 && argc >= 3) {
        return cmd_verify(argv[2]);
    } else if (strcmp(cmd, "sign") == 0 && argc >= 3) {
        return cmd_sign(argv[2], NULL);
    } else if (strcmp(cmd, "compile") == 0 && argc >= 3) {
        return cmd_compile(argv[2], NULL);
    } else if (strcmp(cmd, "cosign") == 0 && argc >= 3) {
        int rc = cmd_cosign(argv[2], NULL);
        if (rc == 0) lock_file_readonly(argv[2]);
        return rc;
    } else if (strcmp(cmd, "inspect") == 0 && argc >= 3) {
        return cmd_inspect(argv[2]);
    } else if (strcmp(cmd, "redact") == 0) {
        const char* target = (argc >= 3) ? argv[2] : NULL;
        return cmd_redact_terminal(target ? target : "");
    } else if (strcmp(cmd, "render") == 0 && argc >= 3) {
        const char* out_path = (argc >= 4) ? argv[3] : NULL;
        return cmd_render_forward(argv[2], out_path);
    } else if (strcmp(cmd, "audit") == 0) {
        return cmd_audit(argc, argv);
    } else if (strcmp(cmd, "--inject-property") == 0 && argc >= 4) {
        return cmd_inject_property_forward(argv[2], argv[3]);
    } else if (strcmp(cmd, "--extract-property") == 0 && argc >= 3) {
        const char* out_dir = "./extracted_ip";
        for (int i = 3; i < argc; ++i) {
            if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
                out_dir = argv[i + 1];
                break;
            }
        }
        return cmd_extract_property_forward(argv[2], out_dir);
    } else if (strcmp(cmd, "--export-office") == 0 && argc >= 3) {
        return cmd_export_office(argv[2]);
    } else {
        print_usage(argv[0]);
        return 1;
    }
}
