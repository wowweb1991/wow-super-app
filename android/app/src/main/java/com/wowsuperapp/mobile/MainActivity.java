package com.wowsuperapp.mobile;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.content.Intent;
import android.net.Uri;
public class MainActivity extends Activity {
 private WebView web;
 private static final String HOME="https://wow-super-app.onrender.com/";
 @Override public void onCreate(Bundle state){super.onCreate(state);web=new WebView(this);setContentView(web);web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.setWebChromeClient(new WebChromeClient());web.setWebViewClient(new WebViewClient(){@Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){Uri uri=request.getUrl();if("wow-super-app.onrender.com".equalsIgnoreCase(uri.getHost())&&"https".equalsIgnoreCase(uri.getScheme()))return false;startActivity(new Intent(Intent.ACTION_VIEW,uri));return true;}});web.loadUrl(HOME);}
 @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
 @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
