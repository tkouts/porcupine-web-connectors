-------------------------------------
Porcupine MOD_PYTHON Apache connector
-------------------------------------

1. Before installing ensure that the web server has Python 2.3.x or later installed.
2. If installing on Apache 1.3.x then MOD_PYTHON 2.7.x is required.
   If installing on Apache 2.x then MOD_PYTHON 3.1.x is required.
3. To install, first unpack the contents to the apache's root directory.
4. Edit server.ini and set the "hosts" setting under the "config" section,
   to the address that Porcupine server is listening.
5. Ensure that mod_python module gets loaded. Search the apache configuration
   file for the following declaration:
	"LoadModule python_module modules/mod_python.so"
6. Edit Apache's "httpd.ini" configuration file. Locate your server's
   root directory configuration section and add the lines marked with the
   arrows ONLY:
   
        #
        # This should be changed to whatever you set DocumentRoot to.
        #
        <Directory "YOUR_SERVER_ROOT">
                ...
                
---->           AddHandler python-program .py
---->           PythonHandler porcupine
---->           PythonDebug On

        </Directory>

7. Open a brower and type "http://SERVER_NAME/porcupine.py".
8. Login with the following credentials:
	Username: admin
	Password: admin

Enjoy!