// Speaker Scribe desktop shell.
//
// Tauri supplies the window and the WebView; the application itself is the local
// FastAPI server, which also serves the built UI. This process starts that
// server, waits for it to answer, points the window at it, and makes sure the
// server dies when the window does.
//
// The Python environment deliberately lives outside the bundle. The speech stack
// runs to gigabytes before any model weights, and MLX compiles Metal shaders at
// runtime, so vendoring it would trade a large amount of fragility for a
// download nobody wants. See docs/packaging.md.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

/// Where the checkout lives. Baked in at build time by scripts/build-app.sh.
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

fn start_server(root: &PathBuf) -> Result<Child, String> {
    Command::new("uv")
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
        .current_dir(root)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|err| {
            format!("Could not start the Speaker Scribe server: {err}.\n\nIs uv installed?")
        })
}

/// Block until the server answers, it dies, or we run out of patience.
fn await_server(child: &mut Child) -> Result<(), String> {
    let deadline = Instant::now() + STARTUP_BUDGET;
    while Instant::now() < deadline {
        if let Ok(Some(status)) = child.try_wait() {
            return Err(format!(
                "The Speaker Scribe server stopped while starting ({status}).\n\nRun ./scripts/check.sh in the project folder to see why."
            ));
        }
        if server_is_up() {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    let _ = child.kill();
    Err("The Speaker Scribe server did not start in time.\n\nThe first run installs dependencies, which can take a while; try again.".into())
}

fn fail(message: &str) -> ! {
    // No window yet, so report through the system rather than the UI.
    let _ = Command::new("osascript")
        .args([
            "-e",
            &format!(
                r#"display alert "Speaker Scribe" message "{}" as critical"#,
                message.replace('"', "'")
            ),
        ])
        .status();
    eprintln!("{message}");
    std::process::exit(1);
}

fn main() {
    let root = PathBuf::from(PROJECT_ROOT);
    if !root.join("backend").is_dir() {
        fail(&format!(
            "The project folder has moved.\n\nExpected it at {PROJECT_ROOT}. Rebuild with scripts/build-app.sh."
        ));
    }

    let owned: Option<Child> = if server_is_up() {
        None
    } else {
        let mut child = match start_server(&root) {
            Ok(child) => child,
            Err(message) => fail(&message),
        };
        if let Err(message) = await_server(&mut child) {
            fail(&message);
        }
        Some(child)
    };

    tauri::Builder::default()
        .manage(Backend(Mutex::new(owned)))
        .setup(|app| {
            WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::External(app_url().parse().expect("valid local url")),
            )
            .title("Speaker Scribe")
            .inner_size(1280.0, 860.0)
            .min_inner_size(900.0, 600.0)
            .build()?;
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
