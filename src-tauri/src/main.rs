// Speaker Scribe desktop shell.
//
// Tauri supplies the window and the WebView; the application itself is the local
// FastAPI server, which also serves the built UI. This process starts that
// server, waits for it to answer, and points the window at it.
//
// A release bundle carries everything it needs in Contents/Resources: a
// relocatable CPython with the speech stack installed into it, the backend
// source, the built UI, and a decode-only ffmpeg. Such a build runs on a machine
// with no Python, no Homebrew and no toolchain. A development build has no such
// resources and falls back to `uv run` against this checkout.
//
// The runtime is installed into the interpreter rather than a virtualenv on
// purpose: a venv stores the absolute path of its base interpreter and reads it
// at every startup, so one built here would keep pointing at this checkout after
// being copied into a bundle. See scripts/build-runtime.sh.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

/// Where the checkout lives. Baked in at build time by scripts/build-app.sh, and
/// used only by development builds that have no bundled runtime.
const PROJECT_ROOT: &str = env!("SPEAKER_SCRIBE_ROOT");
const PORT: &str = "8118";
const STARTUP_BUDGET: Duration = Duration::from_secs(240);

/// Holds the server process so it can be stopped when the app exits.
struct Backend(Mutex<Option<Child>>);

fn health_url() -> String {
    format!("http://127.0.0.1:{PORT}/api/health")
}

fn app_url() -> String {
    format!("http://127.0.0.1:{PORT}/")
}

/// How this build reaches a Python that can run the server.
enum Runtime {
    /// A release bundle: interpreter, backend, UI and ffmpeg all in Resources.
    Bundled { resources: PathBuf },
    /// A development build: the checkout, driven through uv.
    Checkout,
}

impl Runtime {
    /// Prefer the bundled runtime, and only fall back when it is genuinely
    /// absent. Silently falling back when a bundled interpreter is present but
    /// broken would turn a packaging fault into a confusing "is uv installed?".
    fn detect(resources: Option<PathBuf>) -> Runtime {
        match resources {
            Some(dir) if dir.join("runtime/bin/python3").is_file() => {
                Runtime::Bundled { resources: dir }
            }
            _ => Runtime::Checkout,
        }
    }

    /// Build the server command, including everywhere it should read and write.
    ///
    /// A bundled app must not write inside itself: the bundle is signed, may sit
    /// in a read-only /Applications, and is replaced wholesale on update. So the
    /// data root is passed in from the OS location for application data, while
    /// code and assets are read out of Resources.
    fn server_command(&self, data_dir: &Path) -> Command {
        match self {
            Runtime::Bundled { resources } => {
                let mut command = Command::new(resources.join("runtime/bin/python3"));
                command
                    .args([
                        "-m",
                        "uvicorn",
                        "speaker_scribe_backend.app:app",
                        "--app-dir",
                    ])
                    .arg(resources.join("backend"))
                    .args(["--host", "127.0.0.1", "--port", PORT])
                    .env("SPEAKER_SCRIBE_DATA", data_dir)
                    .env("SPEAKER_SCRIBE_UI", resources.join("dist"))
                    .env("SPEAKER_SCRIBE_FFMPEG", resources.join("ffmpeg"))
                    // Weights are downloaded and deleted by the user, so their
                    // caches live beside the data rather than in the signed,
                    // read-only bundle. The models shipped inside the bundle are
                    // copied out into them on first run.
                    .env("HF_HOME", data_dir.join("models"))
                    .env("SPEAKER_SCRIBE_MODEL_CACHE", data_dir.join("model-cache"))
                    .env("SPEAKER_SCRIBE_BUNDLED_MODELS", resources.join("models"))
                    // mlx-whisper shells out to ffmpeg by name, so the bundled
                    // one has to be findable as a plain `ffmpeg` too.
                    .env("PATH", bundled_path(resources));
                command
            }
            Runtime::Checkout => {
                let mut command = Command::new("uv");
                command
                    .args([
                        "run",
                        "--extra",
                        "ml",
                        "uvicorn",
                        "speaker_scribe_backend.app:app",
                        "--app-dir",
                        "backend",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        PORT,
                    ])
                    .current_dir(PROJECT_ROOT);
                command
            }
        }
    }

    fn failure_hint(&self) -> &'static str {
        match self {
            Runtime::Bundled { .. } => {
                "The bundled speech engine did not start. Reinstalling Speaker Scribe should fix it."
            }
            Runtime::Checkout => {
                "Run ./scripts/check.sh in the project folder to see why. A development build needs uv on PATH."
            }
        }
    }
}

/// PATH with the bundle's own tools first, so `ffmpeg` resolves to the copy that
/// ships with the app whether or not the user has one installed.
fn bundled_path(resources: &Path) -> String {
    let inherited = std::env::var("PATH").unwrap_or_default();
    // ffmpeg is bundled as a file named `ffmpeg`; its directory is what PATH needs.
    match resources.join("ffmpeg").parent() {
        Some(dir) => format!("{}:{inherited}", dir.display()),
        None => inherited,
    }
}

/// True when something already answers on the port, so a second copy of the
/// server is never started.
fn server_is_up() -> bool {
    Command::new("curl")
        .args(["-fsS", "--max-time", "2", &health_url()])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

/// Block until the server answers, it dies, or we run out of patience.
fn await_server(child: &mut Child, runtime: &Runtime) -> Result<(), String> {
    let deadline = Instant::now() + STARTUP_BUDGET;
    while Instant::now() < deadline {
        if let Ok(Some(status)) = child.try_wait() {
            return Err(format!(
                "The Speaker Scribe server stopped while starting ({status}).\n\n{}",
                runtime.failure_hint()
            ));
        }
        if server_is_up() {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    let _ = child.kill();
    Err(format!(
        "The Speaker Scribe server did not start in time.\n\n{}",
        runtime.failure_hint()
    ))
}

/// Start the server unless one is already running. `Ok(None)` means an existing
/// server was adopted, and must not be killed on exit.
fn ensure_server(runtime: &Runtime, data_dir: &Path) -> Result<Option<Child>, String> {
    if server_is_up() {
        return Ok(None);
    }

    let mut child = runtime
        .server_command(data_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|err| {
            format!(
                "Could not start the Speaker Scribe server: {err}.\n\n{}",
                runtime.failure_hint()
            )
        })?;

    await_server(&mut child, runtime)?;
    Ok(Some(child))
}

/// Report a startup failure in the window that is already open, rather than in a
/// system dialog with nothing behind it.
fn show_failure(window: &WebviewWindow, message: &str) {
    let escaped = message
        .replace('\\', "\\\\")
        .replace('`', "\\`")
        .replace("${", "\\${");
    let _ = window.eval(&format!(
        "document.body.classList.add('failed');\
         document.getElementById('title').textContent = 'Speaker Scribe could not start';\
         document.getElementById('detail').textContent = `{escaped}`;"
    ));
    eprintln!("{message}");
}

fn main() {
    tauri::Builder::default()
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            // Open immediately on the loading page. Waiting for the server first
            // leaves the user with no window at all through a cold start, which
            // reads as a launch failure.
            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("loading.html".into()))
                    .title("Speaker Scribe")
                    .inner_size(1280.0, 860.0)
                    .min_inner_size(900.0, 600.0)
                    .build()?;

            let runtime = Runtime::detect(app.path().resource_dir().ok());
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;

            let handle = app.handle().clone();
            std::thread::spawn(move || match ensure_server(&runtime, &data_dir) {
                Ok(owned) => {
                    if let Some(state) = handle.try_state::<Backend>() {
                        if let Ok(mut slot) = state.0.lock() {
                            *slot = owned;
                        }
                    }
                    match app_url().parse() {
                        Ok(url) => {
                            let _ = window.navigate(url);
                        }
                        Err(err) => show_failure(&window, &format!("Bad server address: {err}")),
                    }
                }
                Err(message) => show_failure(&window, &message),
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to start Speaker Scribe")
        .run(|handle, event| {
            // Only stop the server if this process was the one that started it;
            // a server the user was already running is left alone.
            if let RunEvent::Exit = event {
                if let Some(state) = handle.try_state::<Backend>() {
                    if let Ok(mut slot) = state.0.lock() {
                        if let Some(mut child) = slot.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        });
}
