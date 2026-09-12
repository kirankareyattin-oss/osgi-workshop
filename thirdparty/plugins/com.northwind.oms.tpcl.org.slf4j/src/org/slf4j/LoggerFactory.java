package org.slf4j;

public final class LoggerFactory {

    private LoggerFactory() {
    }

    public static Logger getLogger(Class<?> type) {
        return getLogger(type.getName());
    }

    public static Logger getLogger(String name) {
        return new ConsoleLogger(name);
    }

    private static final class ConsoleLogger implements Logger {

        private final String name;

        ConsoleLogger(String name) {
            this.name = name;
        }

        @Override
        public boolean isInfoEnabled() {
            return true;
        }

        @Override
        public void info(String message) {
            System.out.println("INFO  " + name + " - " + message);
        }

        @Override
        public void warn(String message) {
            System.out.println("WARN  " + name + " - " + message);
        }

        @Override
        public void error(String message) {
            System.err.println("ERROR " + name + " - " + message);
        }

        @Override
        public void error(String message, Throwable throwable) {
            System.err.println("ERROR " + name + " - " + message);
            throwable.printStackTrace();
        }
    }
}
