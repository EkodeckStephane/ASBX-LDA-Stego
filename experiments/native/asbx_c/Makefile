CC ?= gcc
CFLAGS ?= -O3 -std=c11 -Wall -Wextra -pedantic
LDFLAGS ?=

TARGET = asbxc
OBJS = asbx.o asbx_cli.o

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)

asbx.o: asbx.c asbx.h
	$(CC) $(CFLAGS) -c asbx.c

asbx_cli.o: asbx_cli.c asbx.h
	$(CC) $(CFLAGS) -c asbx_cli.c

clean:
	rm -f $(TARGET) $(TARGET).exe $(OBJS)
