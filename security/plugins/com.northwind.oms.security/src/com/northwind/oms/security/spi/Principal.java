package com.northwind.oms.security.spi;

import java.util.Set;

/**
 * An authenticated actor together with the roles granted to it.
 * Contributed by the security bundle and consumed by auditing/authorization code.
 */
public interface Principal {

    String getName();

    Set<String> getRoles();

    default boolean hasRole(String role) {
        return getRoles().contains(role);
    }
}
