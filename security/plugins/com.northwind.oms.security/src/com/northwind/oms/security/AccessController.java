package com.northwind.oms.security;

import java.util.Set;

import com.northwind.oms.security.spi.Principal;

/**
 * Evaluates whether a {@link Principal} is permitted to perform a named action.
 * A tiny, deliberately naive role-based check used for the assessment.
 */
public class AccessController {

    public boolean isAllowed(Principal principal, String requiredRole) {
        if (principal == null || requiredRole == null) {
            return false;
        }
        return principal.hasRole(requiredRole) || principal.hasRole("ADMIN");
    }

    public void checkPermission(Principal principal, String requiredRole) {
        if (!isAllowed(principal, requiredRole)) {
            throw new SecurityException("Access denied: '"
                    + (principal == null ? "anonymous" : principal.getName())
                    + "' lacks role " + requiredRole);
        }
    }

    public static Principal anonymous() {
        return new Principal() {
            @Override
            public String getName() {
                return "anonymous";
            }

            @Override
            public Set<String> getRoles() {
                return Set.of();
            }
        };
    }
}
