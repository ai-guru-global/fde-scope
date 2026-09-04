package io.github.aiguru.fdescopeweb;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {

    private static final String DEMO_URL = "file:///android_asset/demo/index.html";

    private WebView web;
    private View setup;
    private EditText serverInput;
    private SharedPreferences prefs;
    private boolean themeSeeded;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("fde_scope", Context.MODE_PRIVATE);

        int bg = getColor(R.color.fde_bg);
        getWindow().setStatusBarColor(bg);
        if (!isNight()) {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        }

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(bg);

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        root.addView(column, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        column.addView(buildToolbar(),
                new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        web = new WebView(this);
        web.setBackgroundColor(bg);
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

            @Override
            public void onPageFinished(WebView view, String url) {
                if (!themeSeeded) {
                    themeSeeded = true;
                    String t = isNight() ? "dark" : "light";
                    view.evaluateJavascript(
                            "(function(){try{if(!localStorage.getItem('fde-theme')){"
                                    + "localStorage.setItem('fde-theme','" + t + "');"
                                    + "document.documentElement.dataset.theme='" + t + "';}}catch(e){}})();",
                            null);
                }
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
        LinearLayout wrap = new LinearLayout(this);
        wrap.setOrientation(LinearLayout.VERTICAL);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(14), dp(8), dp(8), dp(8));
        bar.setBackgroundColor(getColor(R.color.fde_panel));

        TextView brand = new TextView(this);
        brand.setText("FDE Scope Console");
        brand.setTextSize(14);
        brand.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        brand.setTextColor(getColor(R.color.fde_fg));
        bar.addView(brand);

        View spacer = new View(this);
        bar.addView(spacer, new LinearLayout.LayoutParams(0, 1, 1f));

        bar.addView(toolbarButton("演示", v -> web.loadUrl(DEMO_URL)));
        bar.addView(toolbarButton("换址", v -> showSetup()));
        bar.addView(toolbarButton("刷新", v -> web.reload()));

        wrap.addView(bar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        View line = new View(this);
        line.setBackgroundColor(getColor(R.color.fde_border));
        wrap.addView(line, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(1)));
        return wrap;
    }

    private View toolbarButton(String label, View.OnClickListener onClick) {
        TextView b = new TextView(this);
        b.setText(label);
        b.setTextSize(13);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        b.setTextColor(textStates(getColor(R.color.fde_muted), getColor(R.color.fde_fg)));
        b.setPadding(dp(12), dp(7), dp(12), dp(7));
        b.setBackground(ghostBg());
        b.setOnClickListener(onClick);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.leftMargin = dp(4);
        return b;
    }

    private View buildSetupPanel() {
        FrameLayout scrim = new FrameLayout(this);
        scrim.setBackgroundColor(getColor(R.color.fde_bg));

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(24), dp(26), dp(24), dp(22));
        GradientDrawable cardBg = new GradientDrawable();
        cardBg.setColor(getColor(R.color.fde_panel));
        cardBg.setCornerRadius(dp(10));
        cardBg.setStroke(dp(1), getColor(R.color.fde_border));
        card.setBackground(cardBg);
        card.setElevation(dp(3));

        TextView title = new TextView(this);
        title.setText("连接 FDE Scope");
        title.setTextSize(22);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        title.setTextColor(getColor(R.color.fde_fg));
        card.addView(title);

        TextView hint = new TextView(this);
        hint.setText("输入 fde-scope web 服务器地址（与电脑同一局域网，如 http://192.168.1.10:8080）");
        hint.setTextSize(14);
        hint.setTextColor(getColor(R.color.fde_muted));
        hint.setLineSpacing(dp(3), 1f);
        hint.setPadding(0, dp(10), 0, dp(20));
        card.addView(hint);

        serverInput = new EditText(this);
        serverInput.setSingleLine(true);
        serverInput.setTextSize(15);
        serverInput.setTypeface(Typeface.MONOSPACE);
        serverInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        serverInput.setImeOptions(EditorInfo.IME_ACTION_GO);
        serverInput.setTextColor(getColor(R.color.fde_fg));
        serverInput.setHintTextColor(getColor(R.color.fde_faint));
        serverInput.setHint("http://192.168.1.10:8080");
        serverInput.setText(prefs.getString("server", "http://"));
        serverInput.setSelectAllOnFocus(true);
        serverInput.setPadding(dp(12), dp(12), dp(12), dp(12));
        serverInput.setBackground(inputBg(false));
        serverInput.setOnFocusChangeListener((v, has) -> serverInput.setBackground(inputBg(has)));
        serverInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_GO) {
                connectFromInput();
                return true;
            }
            return false;
        });
        card.addView(serverInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(0, dp(20), 0, 0);
        row.addView(primaryButton("连接", v -> connectFromInput()),
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        LinearLayout.LayoutParams ghostLp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        ghostLp.leftMargin = dp(10);
        row.addView(secondaryButton("内置演示", v -> {
            setup.setVisibility(View.GONE);
            web.loadUrl(DEMO_URL);
        }), ghostLp);
        card.addView(row, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView meta = new TextView(this);
        meta.setText("FDE Scope Console · v" + versionName());
        meta.setTextSize(11);
        meta.setTypeface(Typeface.MONOSPACE);
        meta.setTextColor(getColor(R.color.fde_faint));
        meta.setPadding(0, dp(20), 0, 0);
        card.addView(meta);

        DisplayMetrics dm = getResources().getDisplayMetrics();
        int cardWidth = Math.min(dp(420), dm.widthPixels - dp(40));
        scrim.addView(card, new FrameLayout.LayoutParams(
                cardWidth, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER));
        return scrim;
    }

    private TextView primaryButton(String label, View.OnClickListener onClick) {
        TextView b = new TextView(this);
        b.setText(label);
        b.setGravity(Gravity.CENTER);
        b.setTextSize(15);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        b.setTextColor(getColor(R.color.fde_accent_ink));
        b.setPadding(dp(14), dp(12), dp(14), dp(12));
        b.setBackground(fillBg(getColor(R.color.fde_accent), getColor(R.color.fde_accent_2), dp(7)));
        b.setOnClickListener(onClick);
        return b;
    }

    private TextView secondaryButton(String label, View.OnClickListener onClick) {
        TextView b = new TextView(this);
        b.setText(label);
        b.setGravity(Gravity.CENTER);
        b.setTextSize(15);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        b.setTextColor(getColor(R.color.fde_fg));
        b.setPadding(dp(14), dp(12), dp(14), dp(12));
        GradientDrawable content = new GradientDrawable();
        content.setColor(getColor(R.color.fde_panel));
        content.setCornerRadius(dp(7));
        content.setStroke(dp(1), getColor(R.color.fde_border));
        b.setBackground(rippleWith(content, getColor(R.color.fde_panel2)));
        b.setOnClickListener(onClick);
        return b;
    }

    private void connectFromInput() {
        String url = serverInput.getText().toString().trim();
        if (url.isEmpty()) {
            Toast.makeText(this, "请输入服务器地址", Toast.LENGTH_SHORT).show();
            return;
        }
        if (!url.contains("://")) {
            url = "http://" + url;
        }
        hideKeyboard();
        prefs.edit().putString("server", url).apply();
        setup.setVisibility(View.GONE);
        web.loadUrl(url);
    }

    private void showSetup() {
        setup.setVisibility(View.VISIBLE);
    }

    private void hideKeyboard() {
        InputMethodManager imm =
                (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        View focus = getCurrentFocus();
        if (imm != null && focus != null) {
            imm.hideSoftInputFromWindow(focus.getWindowToken(), 0);
        }
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

    private Drawable ghostBg() {
        GradientDrawable content = new GradientDrawable();
        content.setCornerRadius(dp(6));
        content.setColor(Color.TRANSPARENT);
        return rippleWith(content, getColor(R.color.fde_panel2));
    }

    private Drawable fillBg(int rest, int pressed, int radius) {
        GradientDrawable content = new GradientDrawable();
        content.setColor(rest);
        content.setCornerRadius(radius);
        return rippleWith(content, pressed);
    }

    private Drawable rippleWith(GradientDrawable content, int pressedColor) {
        return new RippleDrawable(
                new ColorStateList(
                        new int[][]{{android.R.attr.state_pressed}, {}},
                        new int[]{pressedColor, Color.TRANSPARENT}),
                content, null);
    }

    private ColorStateList textStates(int rest, int pressed) {
        return new ColorStateList(
                new int[][]{{android.R.attr.state_pressed}, {}},
                new int[]{pressed, rest});
    }

    private Drawable inputBg(boolean focused) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(getColor(R.color.fde_code));
        d.setCornerRadius(dp(7));
        d.setStroke(dp(1), focused
                ? getColor(R.color.fde_accent)
                : getColor(R.color.fde_border_strong));
        return d;
    }

    private String versionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "?";
        }
    }

    private boolean isNight() {
        int mask = getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK;
        return mask == Configuration.UI_MODE_NIGHT_YES;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
