package io.github.aiguru.fdescopeweb;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {

    private static final String DEMO_URL = "file:///android_asset/demo/index.html";

    private WebView web;
    private LinearLayout setup;
    private EditText serverInput;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("fde_scope", Context.MODE_PRIVATE);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(0xF7, 0xF9, 0xFC));

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        root.addView(column, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        column.addView(buildToolbar(),
                new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        web = new WebView(this);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                String scheme = u.getScheme() == null ? "" : u.getScheme();
                if (scheme.equals("http") || scheme.equals("https") || scheme.equals("file")) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (Exception ignored) {
                }
                return true;
            }
        });
        column.addView(web, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setup = buildSetupPanel();
        setup.setVisibility(View.GONE);
        root.addView(setup, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        setContentView(root);

        String saved = prefs.getString("server", "");
        if (saved.isEmpty()) {
            showSetup();
        } else {
            web.loadUrl(saved);
        }
    }

    private View buildToolbar() {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(12), dp(8), dp(12), dp(8));
        bar.setBackgroundColor(Color.WHITE);

        bar.addView(toolbarButton("演示", v -> web.loadUrl(DEMO_URL)));
        bar.addView(toolbarButton("换址", v -> showSetup()));
        bar.addView(toolbarButton("刷新", v -> web.reload()));
        return bar;
    }

    private View toolbarButton(String label, View.OnClickListener onClick) {
        TextView b = new TextView(this);
        b.setText(label);
        b.setTextSize(13);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setTextColor(Color.rgb(0x30, 0x3F, 0x54));
        b.setPadding(dp(14), dp(6), dp(14), dp(6));
        b.setBackgroundResource(android.R.drawable.dialog_holo_light_frame);
        b.setOnClickListener(v -> {
            b.setBackgroundColor(Color.rgb(0xED, 0xF1, 0xF7));
            onClick.onClick(v);
            b.setBackgroundColor(Color.TRANSPARENT);
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.leftMargin = dp(8);
        return b;
    }

    private LinearLayout buildSetupPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setGravity(Gravity.CENTER);
        panel.setPadding(dp(28), dp(28), dp(28), dp(28));
        panel.setBackgroundColor(Color.rgb(0xF7, 0xF9, 0xFC));

        TextView title = new TextView(this);
        title.setText("连接 FDE Scope");
        title.setTextSize(22);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(0x1D, 0x29, 0x39));
        panel.addView(title);

        TextView hint = new TextView(this);
        hint.setText("输入 fde-scope web 服务器地址\n（与电脑同一局域网，如 http://192.168.1.10:8080）");
        hint.setTextSize(14);
        hint.setTextColor(Color.rgb(0x5A, 0x6B, 0x82));
        hint.setPadding(0, dp(10), 0, dp(18));
        panel.addView(hint);

        serverInput = new EditText(this);
        serverInput.setSingleLine(true);
        serverInput.setTextSize(15);
        serverInput.setHint("http://192.168.1.10:8080");
        serverInput.setText(prefs.getString("server", "http://"));
        panel.addView(serverInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        row.setPadding(0, dp(18), 0, 0);

        Button connect = new Button(this);
        connect.setText("连接");
        connect.setTextColor(Color.WHITE);
        connect.getBackground().setColorFilter(Color.rgb(0x2F, 0x6F, 0xEB), android.graphics.PorterDuff.Mode.SRC_ATOP);
        connect.setOnClickListener(v -> {
            String url = serverInput.getText().toString().trim();
            if (url.isEmpty()) {
                Toast.makeText(this, "请输入服务器地址", Toast.LENGTH_SHORT).show();
                return;
            }
            if (!url.contains("://")) {
                url = "http://" + url;
            }
            connect(url);
        });
        row.addView(connect, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button demo = new Button(this);
        demo.setText("内置演示");
        demo.setTextColor(Color.rgb(0x30, 0x3F, 0x54));
        demo.getBackground().setColorFilter(Color.rgb(0xE3, 0xE9, 0xF2), android.graphics.PorterDuff.Mode.SRC_ATOP);
        demo.setOnClickListener(v -> {
            setup.setVisibility(View.GONE);
            web.loadUrl(DEMO_URL);
        });
        LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        dlp.leftMargin = dp(12);
        row.addView(demo, dlp);

        panel.addView(row, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return panel;
    }

    private void connect(String url) {
        prefs.edit().putString("server", url).apply();
        setup.setVisibility(View.GONE);
        web.loadUrl(url);
    }

    private void showSetup() {
        setup.setVisibility(View.VISIBLE);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (setup.getVisibility() == View.VISIBLE
                    && !prefs.getString("server", "").isEmpty()) {
                setup.setVisibility(View.GONE);
                return true;
            }
            if (web.canGoBack()) {
                web.goBack();
                return true;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
