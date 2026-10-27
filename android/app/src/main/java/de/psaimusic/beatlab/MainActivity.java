package de.psaimusic.beatlab;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public class MainActivity extends Activity {
    private static final String HOME = "https://gmd-pforte.github.io/BEATLAP/";
    private static final String HOST = "gmd-pforte.github.io";
    private static final int PICK_FILE = 9021;
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private volatile boolean trustedPage = false;
    private final Map<String, DownloadSession> downloads = new ConcurrentHashMap<>();

    private static final class DownloadSession {
        final Uri uri;
        final OutputStream stream;
        long size = 0L;
        DownloadSession(Uri uri, OutputStream stream) {
            this.uri = uri;
            this.stream = stream;
        }
    }

    private boolean isTrusted(Uri uri) {
        return uri != null && "https".equalsIgnoreCase(uri.getScheme())
                && HOST.equalsIgnoreCase(uri.getHost())
                && uri.getPath() != null && uri.getPath().startsWith("/BEATLAP/");
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(11, 9, 16));
        getWindow().setNavigationBarColor(Color.rgb(11, 9, 16));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(11, 9, 16));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(true);
        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);

        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        webView.addJavascriptInterface(new BeatlabBridge(), "BeatlabAndroid");

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try {
                    startActivityForResult(params.createIntent(), PICK_FILE);
                    return true;
                } catch (ActivityNotFoundException ex) {
                    fileCallback = null;
                    callback.onReceiveValue(null);
                    toast("Keine Datei-App gefunden.");
                    return false;
                }
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (isTrusted(url)) return false;
                if ("about".equals(url.getScheme())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                } catch (Exception ex) {
                    toast("Link konnte nicht geöffnet werden.");
                }
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                trustedPage = isTrusted(Uri.parse(url));
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) showOffline();
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request,
                                            WebResourceResponse response) {
                if (request.isForMainFrame() && response.getStatusCode() >= 400) showOffline();
            }
        });

        openStudio();
    }

    private void openStudio() {
        trustedPage = false;
        webView.loadUrl(HOME + "?app=android&t=" + System.currentTimeMillis());
    }

    private void showOffline() {
        trustedPage = false;
        try (InputStream input = getAssets().open("offline.html");
             ByteArrayOutputStream data = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[8192];
            int size;
            while ((size = input.read(chunk)) != -1) data.write(chunk, 0, size);
            String html = data.toString(StandardCharsets.UTF_8.name());
            runOnUiThread(() -> webView.loadDataWithBaseURL(
                    "https://appassets.androidplatform.net/", html, "text/html", "UTF-8", null));
        } catch (Exception ex) {
            toast("Keine Internetverbindung. Bitte später erneut versuchen.");
        }
    }

    private void toast(String text) {
        runOnUiThread(() -> Toast.makeText(this, text, Toast.LENGTH_LONG).show());
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_FILE && fileCallback != null) {
            Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        for (String id : downloads.keySet()) cancelDownload(id);
        if (webView != null) {
            webView.removeJavascriptInterface("BeatlabAndroid");
            webView.destroy();
        }
        super.onDestroy();
    }

    private void cancelDownload(String id) {
        DownloadSession session = downloads.remove(id);
        if (session == null) return;
        synchronized (session) {
            try { session.stream.close(); } catch (Exception ignored) { }
            getContentResolver().delete(session.uri, null, null);
        }
    }

    public final class BeatlabBridge {
        @JavascriptInterface
        public String beginDownload(String filename, String mime) {
            if (!trustedPage || downloads.size() >= 2) return "";
            try {
                String safe = filename == null ? "beatlab.wav"
                        : filename.replaceAll("[^a-zA-Z0-9._ -]", "_");
                if (safe.length() > 100) safe = safe.substring(safe.length() - 100);
                if (safe.trim().isEmpty()) safe = "beatlab.wav";
                String type = "application/zip".equals(mime) ? "application/zip" : ("application/json".equals(mime) ? "application/json" : "audio/wav");
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, safe);
                values.put(MediaStore.MediaColumns.MIME_TYPE, type);
                values.put(MediaStore.MediaColumns.RELATIVE_PATH,
                        Environment.DIRECTORY_DOWNLOADS + "/PS AI MUSIC");
                values.put(MediaStore.MediaColumns.IS_PENDING, 1);
                Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (uri == null) return "";
                OutputStream stream = getContentResolver().openOutputStream(uri);
                if (stream == null) {
                    getContentResolver().delete(uri, null, null);
                    return "";
                }
                String id = UUID.randomUUID().toString();
                downloads.put(id, new DownloadSession(uri, stream));
                return id;
            } catch (Exception ex) {
                toast("Download konnte nicht gestartet werden.");
                return "";
            }
        }

        @JavascriptInterface
        public boolean writeChunk(String id, String base64) {
            if (!trustedPage || base64 == null || base64.length() > 220000) return false;
            DownloadSession session = downloads.get(id);
            if (session == null) return false;
            try {
                byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
                synchronized (session) {
                    if (session.size + bytes.length > 400L * 1024 * 1024) return false;
                    session.stream.write(bytes);
                    session.size += bytes.length;
                }
                return true;
            } catch (Exception ex) {
                return false;
            }
        }

        @JavascriptInterface
        public boolean finishDownload(String id) {
            if (!trustedPage) return false;
            DownloadSession session = downloads.remove(id);
            if (session == null) return false;
            try {
                synchronized (session) { session.stream.close(); }
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.IS_PENDING, 0);
                getContentResolver().update(session.uri, values, null, null);
                toast("Datei gespeichert: Downloads / PS AI MUSIC");
                return true;
            } catch (Exception ex) {
                getContentResolver().delete(session.uri, null, null);
                return false;
            }
        }

        @JavascriptInterface
        public void cancelDownload(String id) {
            MainActivity.this.cancelDownload(id);
        }

        @JavascriptInterface
        public void retry() {
            runOnUiThread(MainActivity.this::openStudio);
        }
    }
}
