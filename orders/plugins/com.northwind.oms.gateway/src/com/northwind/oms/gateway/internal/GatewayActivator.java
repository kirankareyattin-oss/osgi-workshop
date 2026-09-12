package com.northwind.oms.gateway.internal;

import org.osgi.framework.BundleActivator;
import org.osgi.framework.BundleContext;

/**
 * Controls the gateway bundle life cycle. Registered via the
 * {@code Bundle-Activator} header in {@code META-INF/MANIFEST.MF}.
 */
public class GatewayActivator implements BundleActivator {

    private static BundleContext context;

    static BundleContext getContext() {
        return context;
    }

    @Override
    public void start(BundleContext bundleContext) {
        GatewayActivator.context = bundleContext;
    }

    @Override
    public void stop(BundleContext bundleContext) {
        GatewayActivator.context = null;
    }
}
