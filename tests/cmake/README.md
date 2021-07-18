# cmake example


To run this test.
- start the worker on a machine somewhere and adapt the ~/dist_build/config.json script on that machine
- run the syncer on the machine you want to run the test on and adapt its ~/dist_build/config.json
- run 
```bash
sh run_test.sh
```
here.

To make the test run with a larger input, change run_test.sh to use, for example:
```bash
python create_demo.cc.py 30000 foo > generated_foo.h
python create_demo.cc.py 30000 bar > generated_bar.h
```