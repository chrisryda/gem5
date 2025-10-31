bins:
	aarch64-linux-gnu-gcc -O0 hello_arm64.c -o hello_arm64 --static
	aarch64-linux-gnu-gcc -O0 simple_for.c -o simple_for --static
	aarch64-linux-gnu-gcc -O0 whetstone.c -o whetstone --static -lm
	mv hello_arm64 simple_for whetstone bin/

clean:
	rm bin/hello_arm64 bin/simple_for bin/whetstone
