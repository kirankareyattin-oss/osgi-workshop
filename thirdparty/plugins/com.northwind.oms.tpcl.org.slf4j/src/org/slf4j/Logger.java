package org.slf4j;

/**
 * Minimal SLF4J-style logging facade exposed as a third-party class library
 * (TPCL) bundle. Consumers wire it in through {@code Require-Bundle}.
 */
public interface Logger {

    boolean isInfoEnabled();

    void info(String message);

    void warn(String message);

    void error(String message);

    void error(String message, Throwable throwable);
}
