package com.orunex.mobile;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

public class MainActivity extends Activity {

    private static final int FILE_CHOOSER_REQUEST = 4101;
    private static final String PREFS_NAME = "orunex_mobile";
    private static final String BG_COLOR = "#F8F9FA";

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private Object backCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureWindow();

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor(BG_COLOR));
        root.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor(BG_COLOR));
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setVerticalScrollBarEnabled(false);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        configureWebView(webView);
        root.addView(webView);
        setContentView(root);
        styleSystemBars();
        applyInsets(root);
        webView.loadUrl("file:///android_asset/index.html");

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            OnBackInvokedCallback callback = this::handleBack;
            backCallback = callback;
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, callback);
        }
    }

    private void configureWindow() {
        Window window = getWindow();
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false);
        }
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
    }

    @SuppressWarnings("deprecation")
    private void styleSystemBars() {
        int flags = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        }
        getWindow().getDecorView().setSystemUiVisibility(flags);
    }

    private void applyInsets(View root) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            root.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                view.setPadding(0, bars.top, 0, bars.bottom);
                return insets;
            });
        }
    }

    @SuppressWarnings("deprecation")
    private void configureWebView(WebView view) {
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setTextZoom(100);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            settings.setForceDark(WebSettings.FORCE_DARK_OFF);
        }

        WebView.setWebContentsDebuggingEnabled(true);
        view.addJavascriptInterface(new OrunexBridge(), "OrunexNative");

        view.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView webview, String url) {
                if (url != null && url.startsWith("file:///android_asset/")) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (Exception ignored) {
                }
                return true;
            }
        });

        view.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                    WebView webview,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;
                try {
                    Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("*/*");
                    startActivityForResult(
                            Intent.createChooser(intent, "Choose a file"),
                            FILE_CHOOSER_REQUEST);
                    return true;
                } catch (Exception error) {
                    filePathCallback = null;
                    return false;
                }
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) {
            return;
        }
        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            if (data.getClipData() != null) {
                int count = data.getClipData().getItemCount();
                results = new Uri[count];
                for (int i = 0; i < count; i++) {
                    results[i] = data.getClipData().getItemAt(i).getUri();
                }
            } else if (data.getData() != null) {
                results = new Uri[] { data.getData() };
            }
        }
        filePathCallback.onReceiveValue(results);
        filePathCallback = null;
    }

    @Override
    public void onBackPressed() {
        handleBack();
    }

    private void handleBack() {
        if (webView == null) {
            finish();
            return;
        }
        webView.evaluateJavascript(
                "(function(){try{return window.OrunexHandleBack?window.OrunexHandleBack():false;}catch(e){return false;}})()",
                value -> {
                    Log.d("OrunexBack", "JS back result: " + value);
                    if (!"true".equals(value)) {
                        finish();
                    }
                });
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.onResume();
            webView.resumeTimers();
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
            webView.pauseTimers();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && backCallback instanceof OnBackInvokedCallback) {
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(
                    (OnBackInvokedCallback) backCallback);
            backCallback = null;
        }
        if (webView != null) {
            webView.removeJavascriptInterface("OrunexNative");
            webView.loadUrl("about:blank");
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public class OrunexBridge {

        @JavascriptInterface
        public String loadChats() {
            return prefs().getString("chats_json", "");
        }

        @JavascriptInterface
        public void saveChats(String json) {
            prefs().edit().putString("chats_json", json == null ? "[]" : json).apply();
        }

        @JavascriptInterface
        public String loadSettings() {
            return prefs().getString("settings_json", "");
        }

        @JavascriptInterface
        public void saveSettings(String json) {
            prefs().edit().putString("settings_json", json == null ? "{}" : json).apply();
        }

        @JavascriptInterface
        public String loadUiState() {
            return prefs().getString("ui_state_json", "");
        }

        @JavascriptInterface
        public void saveUiState(String json) {
            prefs().edit().putString("ui_state_json", json == null ? "{}" : json).apply();
        }

        @JavascriptInterface
        public void copyText(String text) {
            runOnUiThread(() -> {
                ClipboardManager clipboard =
                        (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                if (clipboard != null) {
                    clipboard.setPrimaryClip(ClipData.newPlainText("Orunex", text));
                }
                Toast.makeText(MainActivity.this, "Copied to clipboard", Toast.LENGTH_SHORT).show();
            });
        }

        @JavascriptInterface
        public void saveArtifact(String filename, String mime, String base64) {
            String safeName = String.valueOf(filename == null ? "orunex_file" : filename)
                    .replaceAll("[^a-zA-Z0-9._-]", "_");
            String safeMime = (mime == null || mime.trim().isEmpty())
                    ? "application/octet-stream" : mime;
            try {
                byte[] data = Base64.decode(base64 == null ? "" : base64, Base64.DEFAULT);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    ContentValues values = new ContentValues();
                    values.put(MediaStore.MediaColumns.DISPLAY_NAME, safeName);
                    values.put(MediaStore.MediaColumns.MIME_TYPE, safeMime);
                    values.put(MediaStore.MediaColumns.RELATIVE_PATH,
                            Environment.DIRECTORY_DOWNLOADS + "/Orunex");
                    values.put(MediaStore.MediaColumns.IS_PENDING, 1);
                    Uri uri = getContentResolver().insert(
                            MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                    if (uri == null) throw new IllegalStateException("Download store unavailable");
                    try (OutputStream stream = getContentResolver().openOutputStream(uri)) {
                        if (stream == null) throw new IllegalStateException("Could not open download");
                        stream.write(data);
                    }
                    values.clear();
                    values.put(MediaStore.MediaColumns.IS_PENDING, 0);
                    getContentResolver().update(uri, values, null, null);
                } else {
                    File directory = new File(
                            getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "Orunex");
                    if (!directory.exists() && !directory.mkdirs()) {
                        throw new IllegalStateException("Could not create Orunex folder");
                    }
                    File target = new File(directory, safeName);
                    try (FileOutputStream stream = new FileOutputStream(target)) {
                        stream.write(data);
                    }
                }
                runOnUiThread(() -> Toast.makeText(
                        MainActivity.this,
                        "Saved to Downloads/Orunex",
                        Toast.LENGTH_SHORT).show());
            } catch (Exception error) {
                Log.e("OrunexArtifact", "Could not save artifact", error);
                runOnUiThread(() -> Toast.makeText(
                        MainActivity.this,
                        "Could not save artifact",
                        Toast.LENGTH_SHORT).show());
            }
        }

        @JavascriptInterface
        public void setTextZoom(int percent) {
            int zoom = Math.max(80, Math.min(140, percent));
            runOnUiThread(() -> {
                if (webView != null) {
                    webView.getSettings().setTextZoom(zoom);
                }
            });
        }

        @JavascriptInterface
        public void toast(String text) {
            runOnUiThread(() -> Toast.makeText(
                    MainActivity.this, text, Toast.LENGTH_SHORT).show());
        }

        @JavascriptInterface
        public String platform() {
            return "android";
        }

        @JavascriptInterface
        public String version() {
            return "1.0";
        }
    }
}
