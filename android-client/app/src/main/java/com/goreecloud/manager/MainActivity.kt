package com.goreecloud.manager

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.accessibility.AccessibilityManager
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.net.http.SslError
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import kotlin.math.roundToInt

class MainActivity : Activity() {
    companion object {
        const val GLAZE_UI_VERSION = "2.2.0"
        const val GLAZE_UI_SOURCE_REVISION = "6731098b28dd0393faa878c70d989a221d714a20"
        const val GLAZE_TARGET_DP = 48
        const val GLAZE_TOUCH_ASSISTED_DP = 56
        const val GLAZE_SYSTEM_PANEL_BUDGET = 1
    }

    private val managerUri = Uri.parse("https://manager.goreecloud.com/")
    private lateinit var webView: WebView
    private lateinit var errorView: LinearLayout

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this).apply {
            setBackgroundColor(nativeCanvasColor())
            contentDescription = getString(R.string.app_name)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.javaScriptCanOpenWindowsAutomatically = false
            settings.setSupportMultipleWindows(false)
            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.safeBrowsingEnabled = true
            WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
            CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
            webViewClient = SecureManagerClient()
        }

        errorView = buildErrorView()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(nativeCanvasColor())
            addView(webView, LinearLayout.LayoutParams.MATCH_PARENT, 0).also {
                (webView.layoutParams as LinearLayout.LayoutParams).weight = 1f
            }
            addView(errorView, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.MATCH_PARENT)
        }
        setContentView(root)
        showWeb()
        webView.loadUrl(managerUri.toString())
    }

    private fun buildErrorView(): LinearLayout {
        val target = dp(effectiveTargetDp())
        val textColor = nativeTextColor()
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(24), dp(24), dp(24), dp(24))
            setBackgroundColor(nativeRaisedColor())
            visibility = View.GONE

            addView(TextView(context).apply {
                text = getString(R.string.wardveil_error)
                textSize = 18f
                gravity = Gravity.CENTER
                setTextColor(textColor)
                accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
            })
            addView(Button(context).apply {
                text = getString(R.string.retry)
                contentDescription = getString(R.string.retry)
                isAllCaps = false
                minimumHeight = target
                minWidth = target
                setOnClickListener {
                    showWeb()
                    webView.loadUrl(managerUri.toString())
                }
            })
        }
    }

    private fun effectiveTargetDp(): Int {
        val accessibilityManager = getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
        return if (accessibilityManager.isTouchExplorationEnabled) {
            GLAZE_TOUCH_ASSISTED_DP
        } else {
            GLAZE_TARGET_DP
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).roundToInt()

    private fun isDarkAppearance(): Boolean =
        resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES

    private fun nativeCanvasColor(): Int =
        if (isDarkAppearance()) Color.rgb(11, 13, 17) else Color.rgb(245, 247, 250)

    private fun nativeRaisedColor(): Int =
        if (isDarkAppearance()) Color.rgb(27, 32, 40) else Color.rgb(255, 255, 255)

    private fun nativeTextColor(): Int =
        if (isDarkAppearance()) Color.rgb(245, 247, 250) else Color.rgb(21, 26, 35)

    private fun showError() {
        webView.visibility = View.GONE
        errorView.visibility = View.VISIBLE
        errorView.requestFocus()
    }

    private fun showWeb() {
        errorView.visibility = View.GONE
        webView.visibility = View.VISIBLE
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        webView.stopLoading()
        webView.clearHistory()
        webView.removeAllViews()
        webView.destroy()
        super.onDestroy()
    }

    private inner class SecureManagerClient : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val uri = request.url
            val approved = uri.scheme == "https" && uri.host == managerUri.host
            return !approved
        }

        override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
            handler.cancel()
            showError()
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame) showError()
        }

        override fun onPageFinished(view: WebView, url: String) {
            if (Uri.parse(url).host == managerUri.host) showWeb()
        }
    }
}
